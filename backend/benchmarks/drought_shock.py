"""
Task 7.1: Drought Shock Benchmark Scenario
Evaluates farm digital twin resilience and agent decision making under extreme heat,
rapid root-zone moisture depletion, and heightened evapotranspiration (ET0).
"""
import time
from typing import Any, List
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioMetric, ScenarioEvaluationResult
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot
from backend.core.agronomy_models import calculate_fao56_et0


class DroughtShockScenario(BaseScenarioBenchmark):
    """
    Scenario 1: Sudden Drought Shock
    - Temperature: 39.5°C
    - Relative Humidity: 20%
    - Wind: 3.5 m/s
    - Solar Radiation: 27.0 MJ/m2/day
    - Initial soil moisture stressed to ~32-38% across zones.
    """
    def __init__(self):
        super().__init__(
            scenario_id="scenario_drought_shock",
            scenario_name="Drought Shock & Severe Evapotranspiration",
            description="Tests agent responsiveness in averting permanent wilting point under acute heatwave.",
            duration_hours=24.0
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects heatwave weather vector and depresses zone soil moisture."""
        farm.current_weather = WeatherSnapshot(
            temp_c=39.5,
            temp_max=41.0,
            temp_min=24.0,
            humidity_percent=20.0,
            wind_speed_ms=3.5,
            solar_radiation_mj=27.0,
            precipitation_mm=0.0,
            cloud_cover_pct=5.0
        )

        # Deplete soil moisture across all zones to induce drought stress
        for i, zone in enumerate(farm.zones):
            zone.soil_moisture_pct = 31.0 if (i % 2 == 0) else 37.0
            if zone.soil_moisture_pct < 35.0:
                zone.health_status = "water_stressed"

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Calculates intense evaporation over elapsed hours without precipitation."""
        w = farm.current_weather
        et0_daily = calculate_fao56_et0(
            temp_c=w.temp_c,
            humidity_percent=w.humidity_percent,
            wind_speed_2m_ms=w.wind_speed_ms,
            solar_radiation_mj_m2_day=w.solar_radiation_mj
        )
        hourly_depletion = (et0_daily / 24.0) * 1.2  # % moisture lost per hour

        for zone in farm.zones:
            zone.soil_moisture_pct = max(15.0, round(zone.soil_moisture_pct - (hourly_depletion * elapsed_hours), 1))
            if zone.soil_moisture_pct < 30.0:
                zone.health_status = "critically_wilted"
            elif zone.soil_moisture_pct < 35.0:
                zone.health_status = "water_stressed"

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Scores council recommendations, water delivery volume, and wilting prevention."""
        start_t = time.time()
        metrics: List[ScenarioMetric] = []

        # Metric 1: Emergency urgency trigger
        has_emergency_opinion = any(
            op.urgency == "critical" for op in verdict.opinions if hasattr(op, "urgency")
        )
        metrics.append(ScenarioMetric(
            name="Emergency Urgency Detection",
            value=100.0 if has_emergency_opinion else 0.0,
            target=100.0,
            unit="score",
            passed=has_emergency_opinion,
            weight=1.5,
            notes="Council must recognize critical water stress under 35% moisture threshold."
        ))

        # Metric 2: Irrigation commands dispatched
        scheduled = getattr(verdict, "scheduled_actions", [])
        irrigate_actions = [
            a for a in scheduled if a.get("type") in ("irrigate_zone", "irrigate_plot_zones")
        ]
        num_irrigated = len(irrigate_actions)
        target_zones = len([z for z in farm.zones if z.soil_moisture_pct < 50.0])
        irrigation_ratio = min(1.0, num_irrigated / max(1, target_zones)) * 100.0

        metrics.append(ScenarioMetric(
            name="Irrigation Action Coverage",
            value=round(irrigation_ratio, 1),
            target=80.0,
            unit="%",
            passed=irrigation_ratio >= 80.0,
            weight=2.0,
            notes=f"Dispatched {num_irrigated} irrigation action(s) for {target_zones} dry zone(s)."
        ))

        # Metric 3: Wilting Aversion Rate
        non_wilted = sum(1 for z in farm.zones if z.soil_moisture_pct >= 35.0)
        wilting_aversion_rate = (non_wilted / len(farm.zones)) * 100.0
        metrics.append(ScenarioMetric(
            name="Wilting Aversion Rate",
            value=round(wilting_aversion_rate, 1),
            target=70.0,
            unit="%",
            passed=wilting_aversion_rate >= 70.0,
            weight=2.0,
            notes=f"{non_wilted}/{len(farm.zones)} zones preserved above critical wilting boundary."
        ))

        # Calculate weighted score
        total_weight = sum(m.weight for m in metrics)
        weighted_points = sum(min(100.0, (m.value / max(0.001, m.target)) * 100.0) * m.weight for m in metrics)
        final_score = round(min(100.0, weighted_points / total_weight), 1)

        grade = self.compute_composite_grade(final_score)
        passed = final_score >= 70.0
        summary = (
            f"Drought Shock Benchmark: Score {final_score}/100 (Grade {grade}). "
            f"Emergency detected: {has_emergency_opinion}, Actions: {num_irrigated}, "
            f"Wilting aversion: {wilting_aversion_rate:.1f}%."
        )

        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            score=final_score,
            passed=passed,
            grade=grade,
            metrics=metrics,
            summary=summary,
            elapsed_time_s=round(time.time() - start_t, 3)
        )
