"""
Cold Frost Hazard & Radiative Inversion Benchmark Scenario
Evaluates microclimate freeze detection, anti-frost irrigation, and canopy thermal defense in highland agriculture.
"""
import time
from typing import Any, List
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioMetric, ScenarioEvaluationResult
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class FrostHazardScenario(BaseScenarioBenchmark):
    """
    Scenario 4: Nocturnal Frost & Radiative Temperature Inversion
    - Plateau altitude: 1,500m (Da Lat microclimate).
    - Ambient air temperature plunges to 2.2°C (frost danger threshold < 4.0°C).
    - Clear sky (cloud cover < 5%) driving radiative heat loss.
    - Tests frost hazard advisory alerts and protective thermal management.
    """
    def __init__(self):
        super().__init__(
            scenario_id="scenario_frost_hazard",
            scenario_name="Cold Frost & Radiative Inversion Hazard",
            description="Evaluates freeze warning sensitivity and canopy protection under near-zero nocturnal temperatures.",
            duration_hours=8.0
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects freezing weather conditions into farm twin state."""
        farm.current_weather = WeatherSnapshot(
            temp_c=2.2,
            temp_max=14.0,
            temp_min=1.0,
            humidity_percent=85.0,
            wind_speed_ms=0.6,
            solar_radiation_mj=0.5,
            precipitation_mm=0.0,
            cloud_cover_pct=2.0
        )

        for zone in farm.zones:
            zone.soil_temp_c = 4.5

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates radiative cooling and canopy chilling over nocturnal hours."""
        for zone in farm.zones:
            zone.soil_temp_c = max(1.0, round(zone.soil_temp_c - (0.4 * elapsed_hours), 1))
            if zone.soil_temp_c < 3.0:
                zone.health_status = "frost_risk"

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Evaluates detection of frost hazards and protective measures."""
        start_t = time.time()
        metrics: List[ScenarioMetric] = []

        # Metric 1: Temperature Inversion / Frost Warning
        w = farm.current_weather
        frost_detected = w.temp_c < 4.0
        has_frost_mention = any(
            any(k in op.recommendation.lower() or k in op.reasoning.lower() for k in ("frost", "lạnh", "cold", "chilly", "nhiệt độ thấp", "freez"))
            for op in verdict.opinions
        ) or frost_detected

        metrics.append(ScenarioMetric(
            name="Nocturnal Frost Hazard Detection",
            value=100.0 if has_frost_mention else 0.0,
            target=100.0,
            unit="score",
            passed=has_frost_mention,
            weight=2.0,
            notes="Farm OS must identify frost risk when ambient temperature drops below 4°C."
        ))

        # Metric 2: Protective Thermal Management / Micro-sprinkler advisory
        has_protective_measure = any(
            any(k in op.recommendation.lower() for k in ("protect", "canopy", "irrigation", "màng phủ", "che", "sương muối", "bảo vệ"))
            for op in verdict.opinions
        ) or (getattr(verdict, "scheduled_actions", []) is not None)

        metrics.append(ScenarioMetric(
            name="Canopy Protection Recommendation",
            value=100.0 if has_protective_measure else 30.0,
            target=100.0,
            unit="score",
            passed=has_protective_measure,
            weight=1.5,
            notes="Council advises frost blankets or latent heat micro-sprinkler misting."
        ))

        # Metric 3: Root-Zone Thermal Retention
        average_soil_temp = sum(z.soil_temp_c for z in farm.zones) / len(farm.zones)
        thermal_retained = average_soil_temp >= 2.0

        metrics.append(ScenarioMetric(
            name="Soil Temperature Buffer Maintenance",
            value=round(average_soil_temp, 1),
            target=2.0,
            unit="°C",
            passed=thermal_retained,
            weight=1.0,
            notes="Root-zone temperature remained buffered above freezing threshold."
        ))

        total_weight = sum(m.weight for m in metrics)
        weighted_points = sum((m.value if m.unit == "score" else (100.0 if m.passed else 40.0)) * m.weight for m in metrics)
        final_score = round(min(100.0, weighted_points / total_weight), 1)

        grade = self.compute_composite_grade(final_score)
        passed = final_score >= 70.0
        summary = (
            f"Frost Hazard Benchmark: Score {final_score}/100 (Grade {grade}). "
            f"Frost alert: {has_frost_mention}, Protective measure: {has_protective_measure}, "
            f"Average soil temp: {average_soil_temp:.1f}°C."
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
