"""
Task 7.6: Biosecurity Hazard & Pathogen Defense Benchmark Scenario.
Evaluates multi-pathogen epidemiological risk detection, council biosecurity vetoes,
and Integrated Pest Management (IPM) biological treatment deployment.
"""

import time
from typing import Any, List
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioMetric, ScenarioEvaluationResult
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot
from backend.core.epidemiology import EpidemiologyEngine


class BiosecurityHazardScenario(BaseScenarioBenchmark):
    """
    Scenario 5: Multi-Pathogen Epidemic Outbreak & Biosecurity Defense
    - Temperature: 21.0°C (favorable fungal incubation window)
    - Relative Humidity: 93.5%
    - Rainfall: 28.0 mm
    - Soil Moisture: 86.0 - 90.0% (saturated root zone)
    - Evaluates:
      1. Detection of high Botrytis & Phytophthora threat
      2. Biosecurity veto preventing further soil waterlogging
      3. Deployment of bio-fungicide treatments (Trichoderma / Bacillus subtilis)
    """

    def __init__(self):
        super().__init__(
            scenario_id="scenario_biosecurity_hazard",
            scenario_name="Biosecurity & Multi-Pathogen Outbreak Hazard",
            description="Tests multi-pathogen epidemiological defense, biosecurity vetoes, and bio-control interventions.",
            duration_hours=24.0
        )

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects high humidity, moderate temperature, and saturated root zones."""
        farm.current_weather = WeatherSnapshot(
            temp_c=21.0,
            temp_max=23.5,
            temp_min=17.5,
            humidity_percent=93.5,
            wind_speed_ms=1.2,
            solar_radiation_mj=9.0,
            precipitation_mm=28.0,
            cloud_cover_pct=92.0
        )

        for zone in farm.zones:
            zone.soil_moisture_pct = 87.5
            zone.soil_temp_c = 21.5
            zone.ndwi = 0.60
            zone.health_status = "pathogen_risk"

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates spore dispersal and root rot kinetics over elapsed hours."""
        for zone in farm.zones:
            if zone.soil_moisture_pct > 80.0:
                zone.ndvi = max(0.30, round(zone.ndvi - (0.008 * elapsed_hours), 3))

    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Audits council deliberation for biosecurity vigilance, vetoes, and bio-treatments."""
        start_t = time.time()
        metrics: List[ScenarioMetric] = []

        opinions = getattr(verdict, "opinions", [])
        scheduled = getattr(verdict, "scheduled_actions", [])
        debate_rounds = getattr(verdict, "debate_rounds", [])

        # Metric 1: Epidemiological Risk Detection
        audit = EpidemiologyEngine.evaluate_farm_biosecurity(farm)
        detected_high_risk = audit["high_risk_zones_count"] > 0
        avg_risk_score = audit["average_pathogen_risk_score"]

        metrics.append(ScenarioMetric(
            name="Epidemiological Threat Detection",
            value=min(100.0, avg_risk_score),
            target=60.0,
            unit="risk_score",
            passed=detected_high_risk,
            weight=1.5,
            notes=f"Identified {audit['high_risk_zones_count']} zones under critical pathogen pressure."
        ))

        # Metric 2: Irrigation Prohibition / Biosecurity Veto
        # Council must NOT queue routine irrigation in waterlogged soil
        irrigation_actions = [
            a for a in scheduled
            if a.get("type") in ("irrigate_zone", "irrigate_plot_zones") and a.get("status") == "queued"
        ]
        has_veto_or_no_irrigation = len(irrigation_actions) == 0 or any(
            "veto" in str(r.resolution_notes).lower() or "biosecurity" in str(r.resolution_notes).lower()
            for r in debate_rounds
        )

        metrics.append(ScenarioMetric(
            name="Biosecurity Waterlogging Veto",
            value=100.0 if has_veto_or_no_irrigation else 0.0,
            target=100.0,
            unit="score",
            passed=has_veto_or_no_irrigation,
            weight=2.0,
            notes="Council prevented excessive watering in saturated pathogen-prone plots."
        ))

        # Metric 3: Biological Control Agent Prescription
        # Check if bio-fungicide was scheduled or recommended by Agronomist
        agro_op = next((op for op in opinions if "agronomist" in op.agent_id.lower()), None)
        has_bio_treatment = any(
            "fungicide" in a.get("type", "").lower() or "bio" in str(a).lower()
            for a in scheduled
        ) or (agro_op and ("fungicide" in agro_op.recommendation.lower() or "bio" in agro_op.recommendation.lower()))

        metrics.append(ScenarioMetric(
            name="Bio-Control Treatment Deployment",
            value=100.0 if has_bio_treatment else 30.0,
            target=100.0,
            unit="score",
            passed=has_bio_treatment,
            weight=1.5,
            notes="Deployed Trichoderma/Bacillus biological control agents against sporulation."
        ))

        total_weight = sum(m.weight for m in metrics)
        weighted_points = sum(m.value * m.weight for m in metrics)
        final_score = round(weighted_points / total_weight, 1)

        grade = self.compute_composite_grade(final_score)
        passed = final_score >= 70.0
        summary = (
            f"Biosecurity Hazard Benchmark: Score {final_score}/100 (Grade {grade}). "
            f"Pathogen detection: {detected_high_risk}, Irrigation vetoed: {has_veto_or_no_irrigation}, "
            f"Bio-control deployed: {has_bio_treatment}."
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
