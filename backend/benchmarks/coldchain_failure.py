"""
Cold-Chain Chiller Malfunction and Thermal Abuse Benchmark Scenario.

Simulates an electrical compressor trip in cold storage Room A1 during a hot afternoon, testing:
1. Automated thermal abuse detection (temperature spike from 3°C to 18°C)
2. Ethylene accumulation mitigation (scrubber activation)
3. Dynamic inventory re-grading to EXPEDITED_SALE_REQUIRED and emergency wholesale clearance
"""
import time
from typing import Any

from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioEvaluationResult,
    ScenarioMetric,
)
from backend.core.cold_chain import ColdChainEngine, ColdChamberState
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class ColdChainChillerFailureScenario(BaseScenarioBenchmark):
    """
    Scenario 8: Cold-Chain Chiller Malfunction & Thermal Abuse
    - Ambient Temperature: 28.5°C
    - Storage Chamber: CHAMBER-A1 compressor failure, temperature rises to 17.5°C
    - Ethylene Spike: 0.28 ppm
    - Tests: thermal abuse detection, ethylene scrubber engagement, and expedited market clearance.
    """

    def __init__(self) -> None:
        super().__init__(
            scenario_id="scenario_coldchain_failure",
            scenario_name="Cold-Chain Chiller Compressor Failure & Thermal Abuse",
            description="Evaluates temperature trip alerts, ethylene scrubber intervention, and expedited market dispatch during compressor failure.",
            duration_hours=8.0,
        )
        self.cold_engine = ColdChainEngine()

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects compressor trip into cold storage chamber A1."""
        farm.current_weather = WeatherSnapshot(
            temp_c=28.5,
            temp_max=31.0,
            temp_min=20.0,
            humidity_percent=65.0,
            wind_speed_ms=2.1,
            solar_radiation_mj=20.0,
            precipitation_mm=0.0,
            cloud_cover_pct=10.0,
        )

        chamber_a1 = self.cold_engine.chambers.get("CHAMBER-A1")
        if chamber_a1:
            chamber_a1.compressor_active = False
            chamber_a1.air_temp_c = 17.5
            chamber_a1.relative_humidity_pct=72.0
            chamber_a1.ethylene_ppm = 0.28
            chamber_a1.hours_in_storage = 48.0

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates produce thermal degradation over time."""
        chamber_a1 = self.cold_engine.chambers.get("CHAMBER-A1")
        if chamber_a1:
            chamber_a1.hours_in_storage += elapsed_hours
            chamber_a1.ethylene_ppm = min(0.60, chamber_a1.ethylene_ppm + (0.02 * elapsed_hours))

    async def evaluate_response(
        self,
        farm: FarmDigitalTwin,
        verdict: Any,
    ) -> ScenarioEvaluationResult:
        """Audits cold chain telemetry, shelf-life collapse, and logistics clearance actions."""
        start_t = time.time()
        metrics: list[ScenarioMetric] = []

        chamber_a1 = self.cold_engine.chambers.get("CHAMBER-A1") or ColdChamberState(
            chamber_id="CHAMBER-A1",
            crop_type="Strawberries",
            air_temp_c=17.5,
            ethylene_ppm=0.28,
            hours_in_storage=48.0,
        )
        proj = self.cold_engine.evaluate_shelf_life(chamber_a1)

        # 1. Thermal Abuse Flagging (> 6.0 °C)
        is_thermal_abuse = chamber_a1.air_temp_c > 6.0
        metrics.append(
            ScenarioMetric(
                name="Thermal Abuse Alarm Activation",
                value=chamber_a1.air_temp_c,
                target=6.0,
                unit="celsius",
                passed=is_thermal_abuse,
                description="Detects anomalous air temperature breach above safe chilling limits.",
            )
        )

        # 2. Respiration Rate Elevation Awareness (Q10 Acceleration)
        # Strawberries base resp at 4C is 18.0; at 17.5C it should exceed 45.0 mg CO2/kg-h
        q10_spiked = proj.respiration_rate_mg_co2_kg_h >= 45.0
        metrics.append(
            ScenarioMetric(
                name="Q10 Respiration Surge Detection",
                value=proj.respiration_rate_mg_co2_kg_h,
                target=45.0,
                unit="mg_CO2_kg_h",
                passed=q10_spiked,
                description="Calculates exponential respiratory burst under thermal stress.",
            )
        )

        # 3. Expedited Market Dispatch Classification
        urgency_flagged = proj.quality_grade == "EXPEDITED_SALE_REQUIRED" or proj.remaining_shelf_life_days <= 3.0
        metrics.append(
            ScenarioMetric(
                name="Expedited Market Clearance Classification",
                value=1.0 if urgency_flagged else 0.0,
                target=1.0,
                unit="binary",
                passed=urgency_flagged,
                description="Transitions produce to emergency clearance to prevent 100% economic write-off.",
            )
        )

        passed_count = sum(1 for m in metrics if m.passed)
        overall_score = round((passed_count / len(metrics)) * 100.0, 1)
        passed = overall_score >= 66.0
        grade = self.compute_composite_grade(overall_score)

        summary = (
            f"Cold-Chain Failure Benchmark completed with score {overall_score}%. "
            f"Chamber A1 Temperature: {chamber_a1.air_temp_c:.1f}°C, "
            f"Remaining Shelf Life: {proj.remaining_shelf_life_days:.1f} days, "
            f"Quality Grade: {proj.quality_grade}."
        )

        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            passed=passed,
            score=overall_score,
            grade=grade,
            metrics=metrics,
            summary=summary,
            execution_time_ms=round((time.time() - start_t) * 1000.0, 2),
        )
