"""
Task 7.2: Fungal Outbreak Risk Benchmark Scenario
Evaluates plant pathology detection, biocontrol prescription, and microclimate sporulation risk defense.
"""
import time
from typing import Any, List
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioMetric, ScenarioEvaluationResult
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class FungalOutbreakScenario(BaseScenarioBenchmark):
    """
    Scenario 2: Monsoon High-Humidity Fungal Hazard
    - Temperature: 21.5°C (optimal sporulation window: 16-26°C)
    - Relative Humidity: 94.0%
    - Rainfall: 25.0 mm
    - Soil Moisture: 88-92% (water-saturated root zone)
    - High pathogen germination risk (Botrytis cinerea, Phytophthora).
    """
    def __init__(self):
        super().__init__(
            scenario_id="scenario_fungal_outbreak",
            scenario_name="Monsoon Fungal Outbreak & Humidity Hazard",
            description="Tests Agronomist pathology vigilance and bio-fungicide deployment under saturated microclimate.",
            duration_hours=24.0
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects persistent saturated microclimate and waterlogged plot zones."""
        farm.current_weather = WeatherSnapshot(
            temp_c=21.5,
            temp_max=24.0,
            temp_min=18.0,
            humidity_percent=94.0,
            wind_speed_ms=1.1,
            solar_radiation_mj=8.5,
            precipitation_mm=25.0,
            cloud_cover_pct=90.0
        )

        for zone in farm.zones:
            zone.soil_moisture_pct = 88.5
            zone.ndwi = 0.65  # high water index

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates spore germination progression under extended humidity."""
        w = farm.current_weather
        is_spore_active = w.humidity_percent >= 85.0 and (16.0 <= w.temp_c <= 28.0)

        if is_spore_active:
            for zone in farm.zones:
                if zone.soil_moisture_pct > 80.0:
                    zone.ndvi = max(0.35, round(zone.ndvi - (0.01 * elapsed_hours), 2))
                    if zone.health_status != "bio_fungicide_treated":
                        zone.health_status = "fungal_spore_hazard"

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Evaluates pathology warnings, irrigation prohibition, and bio-fungicide dispatch."""
        start_t = time.time()
        metrics: List[ScenarioMetric] = []

        # Metric 1: Agronomist Pathology Detection
        agro_op = next((op for op in verdict.opinions if "agronomist" in op.agent_id.lower()), None)
        has_pathology_alert = False
        if agro_op:
            fungal_count = agro_op.data_points.get("fungal_risk_count", 0)
            has_pathology_alert = fungal_count > 0 or agro_op.urgency in ("critical", "medium")

        metrics.append(ScenarioMetric(
            name="Fungal Pathogen Risk Alert",
            value=100.0 if has_pathology_alert else 0.0,
            target=100.0,
            unit="score",
            passed=has_pathology_alert,
            weight=2.0,
            notes="Agronomist must flag fungal outbreak risk given 94% RH and saturated soils."
        ))

        # Metric 2: Irrigation Suspension (Zero wasteful watering during saturation)
        scheduled = getattr(verdict, "scheduled_actions", [])
        irrigation_actions = [
            a for a in scheduled if a.get("type") in ("irrigate_zone", "irrigate_plot_zones")
        ]
        irrigation_suspended = len(irrigation_actions) == 0

        metrics.append(ScenarioMetric(
            name="Saturation Irrigation Suspension",
            value=100.0 if irrigation_suspended else 0.0,
            target=100.0,
            unit="score",
            passed=irrigation_suspended,
            weight=1.5,
            notes="Hydrology agent must prohibit irrigation while soils exceed field capacity."
        ))

        # Metric 3: Bio-fungicide Treatment Dispatched
        fungicide_actions = [
            a for a in scheduled if "fungicide" in a.get("type", "").lower() or "spray" in a.get("type", "").lower()
        ]
        has_bio_spray = len(fungicide_actions) > 0 or any(
            "fungicide" in op.recommendation.lower() for op in verdict.opinions
        )

        metrics.append(ScenarioMetric(
            name="Preventive Biocontrol Recommendation",
            value=100.0 if has_bio_spray else 0.0,
            target=100.0,
            unit="score",
            passed=has_bio_spray,
            weight=1.5,
            notes="Council must recommend bio-fungicide (Trichoderma) to prevent rot."
        ))

        total_weight = sum(m.weight for m in metrics)
        weighted_points = sum(m.value * m.weight for m in metrics)
        final_score = round(weighted_points / total_weight, 1)

        grade = self.compute_composite_grade(final_score)
        passed = final_score >= 70.0
        summary = (
            f"Fungal Outbreak Benchmark: Score {final_score}/100 (Grade {grade}). "
            f"Pathology alert: {has_pathology_alert}, Irrigation suspended: {irrigation_suspended}, "
            f"Biocontrol applied: {has_bio_spray}."
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
