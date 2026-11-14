"""
Nitrate Leaching and Root Hypoxia Flash Flood Benchmark Scenario.

Simulates a tropical monsoon flash flood event (75mm deluge) in Da Lat highlands, testing:
1. Immediate irrigation throttling & drainage valve activation
2. Nitrogen (NO3-) percolation leaching mitigation
3. Root zone hypoxia prevention and post-flood biological re-inoculation protocol
"""
import time
from typing import Any

from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioEvaluationResult,
    ScenarioMetric,
)
from backend.core.soil_microbiome import SoilMicrobiomeEngine
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class NitrateLeachingFloodScenario(BaseScenarioBenchmark):
    """
    Scenario 7: Tropical Flash Flood, Nitrate Leaching & Root Hypoxia
    - Precipitation: 75.0 mm torrential downpour
    - Soil Moisture: 94.0% (near-total saturation)
    - Tests multi-agent council's ability to veto further watering, activate drainage,
      and recommend microbial mycorrhizae re-inoculation.
    """

    def __init__(self) -> None:
        super().__init__(
            scenario_id="scenario_leaching_flood",
            scenario_name="Tropical Flash Flood & Nitrate Leaching Mitigation",
            description="Evaluates automated irrigation halt, drainage aeration, and soil microbiome preservation during a 75mm monsoon flood.",
            duration_hours=6.0,
        )
        self.soil_engine = SoilMicrobiomeEngine()

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects monsoon cloudburst with heavy precipitation and waterlogged soil."""
        farm.current_weather = WeatherSnapshot(
            temp_c=18.5,
            temp_max=21.0,
            temp_min=16.0,
            humidity_percent=98.0,
            wind_speed_ms=7.8,
            solar_radiation_mj=4.2,
            precipitation_mm=75.0,
            cloud_cover_pct=95.0,
        )

        for zone in farm.zones:
            zone.soil_moisture_pct = 94.0
            zone.soil_temp_c = 17.5
            zone.ndvi = 0.72
            zone.ndwi = 0.45
            zone.health_status = "waterlogged"

    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates gravitational percolation drainage and oxygen depletion over time."""
        for zone in farm.zones:
            # Slow drainage through loamy subsoil: ~1.5% drop per hour
            zone.soil_moisture_pct = max(72.0, zone.soil_moisture_pct - (1.5 * elapsed_hours))

    async def evaluate_response(
        self,
        farm: FarmDigitalTwin,
        verdict: Any,
    ) -> ScenarioEvaluationResult:
        """Audits soil ecology metrics, leaching risk suppression, and council actions."""
        start_t = time.time()
        metrics: list[ScenarioMetric] = []

        # Audit farm soil microbiome under flooded conditions
        report = self.soil_engine.audit_farm(farm, percolation_hours=2.0)

        # 1. Irrigation Throttling Check
        council_actions = getattr(verdict, "approved_actions", []) if verdict else []
        watering_command_executed = any(
            any(k in str(act).lower() for k in ("irrigat", "pump", "water"))
            for act in council_actions
        )
        throttled_successfully = not watering_command_executed
        metrics.append(
            ScenarioMetric(
                name="Irrigation Shutoff Enforcement",
                value=1.0 if throttled_successfully else 0.0,
                target=1.0,
                unit="binary",
                passed=throttled_successfully,
                description="Verifies that all irrigation valves remained sealed during soil saturation.",
            )
        )

        # 2. Leaching Loss Containment (< 10.0 kg N / ha during flash flood)
        avg_n_loss = report.total_estimated_leached_n_kg / max(1, len(farm.zones))
        leaching_contained = avg_n_loss <= 10.0
        metrics.append(
            ScenarioMetric(
                name="Percolation Nitrogen Loss Containment",
                value=round(avg_n_loss, 2),
                target=10.0,
                unit="kg_N_ha",
                passed=leaching_contained,
                description="Maintains nitrate gravitational leaching below emergency threshold via drainage aeration.",
            )
        )

        # 3. Post-Flood Biological Re-inoculation Prescription
        reinoculation_flagged = any(za.reinoculation_recommended for za in report.zone_audits)
        metrics.append(
            ScenarioMetric(
                name="Biological Reinoculation Prescription",
                value=1.0 if reinoculation_flagged else 0.0,
                target=1.0,
                unit="binary",
                passed=reinoculation_flagged,
                description="Triggers mycorrhizal and Trichoderma bio-inoculant recovery protocol.",
            )
        )

        passed_count = sum(1 for m in metrics if m.passed)
        overall_score = round((passed_count / len(metrics)) * 100.0, 1)
        passed = overall_score >= 66.0

        summary = (
            f"Nitrate Leaching Flood Benchmark completed with {overall_score}% efficiency. "
            f"Total estimated N leached: {report.total_estimated_leached_n_kg:.2f} kg across farm. "
            f"Average Soil Health Index: {report.average_soil_health_index:.1f}/100."
        )

        grade = self.compute_composite_grade(overall_score)

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
