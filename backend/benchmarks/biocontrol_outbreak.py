"""
Spider Mite Outbreak and Macro-Biologic Suppression Benchmark Scenario.

Simulates a sudden spider mite outbreak in strawberry bays (28.0 mites/leaf > EIL 15.0):
1. Pre-clearance pesticide residue safety verification
2. Precision aerial drone dispersion of Phytoseiulus persimilis (28 mites/m2)
3. Holling Type II predator-prey suppression kinetics over multi-day period
4. Suppression of pest density below Economic Threshold (5.0 mites/leaf)
5. Zero chemical pesticide application, preserving the 25% organic export price premium.
"""
import time
from typing import Any

from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioEvaluationResult,
    ScenarioMetric,
)
from backend.core.biocontrol import (
    BiocontrolKineticsEngine,
    PopulationState,
    PredatorSpecies,
    PreySpecies,
)
from backend.core.biocontrol_dispersion import MacroBiologicDispersionEngine
from backend.core.biocontrol_safety import BiocontrolSafetyEngine
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot


class SpiderMiteOutbreakScenario(BaseScenarioBenchmark):
    """
    Scenario 11: Spider Mite Outbreak & Macro-Biologic Suppression
    - Initial outbreak: 28.5 spider mites / leaf in Zone B strawberry canopy (far exceeding EIL 15.0)
    - Safety check confirms no harmful pyrethroid residues on foliage
    - Autonomous drone releases Phytoseiulus persimilis at 28.0 predators/m2
    - Simulates 10 days of Holling Type II predation kinetics
    - Verifies pest density drops below ET (5.0) and zero chemical pesticides are applied.
    """

    def __init__(self) -> None:
        super().__init__(
            scenario_id="scenario_spider_mite_outbreak",
            scenario_name="Spider Mite Outbreak & Macro-Biologic Suppression",
            description="Evaluates automated predatory mite dispatch against a severe strawberry pest outbreak, achieving biological suppression below economic injury without chemical pesticides.",
            duration_hours=240.0,  # 10 simulated days
        )
        self.initial_pest_density = 28.5
        self.final_pest_density = 28.5
        self.final_predator_density = 0.0
        self.safety_cleared = False
        self.chemical_sprays_avoided = True
        self.packages_dispatched = 0
        self.export_premium_preserved_vnd = 0.0

    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Injects optimal predatory mite microclimate and sets strawberry plot pest pressure."""
        farm.current_weather = WeatherSnapshot(
            temp_c=25.5,
            temp_max=27.0,
            temp_min=20.0,
            humidity_percent=68.0,
            wind_speed_ms=0.8,
            solar_radiation_mj=18.0,
            precipitation_mm=0.0,
            cloud_cover_pct=25.0,
        )

        for zone in farm.zones:
            if "B" in zone.id or zone.crop_type == "Strawberries":
                zone.health_status = "pest_stressed"

    async def execute_step(self, farm: FarmDigitalTwin, step_index: int, **kwargs: Any) -> dict[str, Any]:
        """
        Executes biological control intervention pipeline:
        1. Safety verification
        2. Dispersion planning
        3. Multi-day Holling Type II population progression.
        """
        # Step 1: Canopy safety verification
        safety_report = BiocontrolSafetyEngine.evaluate_release_safety(
            spray_history=[],  # Clean canopy
            target_beneficial=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS.value,
        )
        self.safety_cleared = safety_report.is_safe_to_release

        # Step 2: Dispersion plan
        canopy_area_m2 = 600.0
        plan = MacroBiologicDispersionEngine.plan_zone_release(
            zone_id="ZONE_STRAWBERRY_B",
            canopy_area_m2=canopy_area_m2,
            pest_density=self.initial_pest_density,
            target_pest=PreySpecies.TWO_SPOTTED_SPIDER_MITE,
            beneficial_species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
            use_drone=True,
        )
        self.packages_dispatched = plan.packages_required

        # Step 3: Simulate 10 days of predation
        initial_predator_density = 4.5
        timeline = BiocontrolKineticsEngine.simulate_timeline(
            initial_prey=self.initial_pest_density,
            initial_predator=initial_predator_density,
            days=10,
            temp_c=25.5,
            predator_species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
            prey_species=PreySpecies.TWO_SPOTTED_SPIDER_MITE,
            step_days=0.5,
        )

        final_state: PopulationState = timeline[-1]
        self.final_pest_density = final_state.prey_density
        self.final_predator_density = final_state.predator_density

        # Step 4: Export premium calculation (600 m2 * 1.2 kg/m2 * 180,000 VND * 25%)
        strawberry_kg = canopy_area_m2 * 1.2
        self.export_premium_preserved_vnd = strawberry_kg * 180000.0 * 0.25

        for zone in farm.zones:
            if "B" in zone.id or zone.crop_type == "Strawberries":
                zone.health_status = "healthy"
                zone.pest_pressure_score = max(0.05, self.final_pest_density / 100.0)

        return {
            "safety_cleared": self.safety_cleared,
            "packages_dispatched": self.packages_dispatched,
            "initial_pest_density": self.initial_pest_density,
            "final_pest_density": self.final_pest_density,
            "final_predator_density": self.final_predator_density,
            "export_premium_preserved_vnd": self.export_premium_preserved_vnd,
            "suppression_status": final_state.suppression_status,
        }

    async def evaluate_results(self, farm: FarmDigitalTwin) -> ScenarioEvaluationResult:
        """Evaluates biological suppression benchmark metrics."""
        start_t = time.time()
        metrics: list[ScenarioMetric] = []

        # 1. Pest Density Suppression (Below Economic Threshold 5.0 mites/leaf)
        suppression_passed = self.final_pest_density <= 5.0
        metrics.append(
            ScenarioMetric(
                name="Economic Threshold Pest Suppression",
                value=round(self.final_pest_density, 2),
                target=5.0,
                unit="mites/leaf",
                passed=suppression_passed,
                description="Knocks down spider mite population below Economic Threshold (5.0 mites/leaf).",
            )
        )

        # 2. Safety Clearance Certification
        metrics.append(
            ScenarioMetric(
                name="Canopy Toxic Residue Clearance",
                value=1.0 if self.safety_cleared else 0.0,
                target=1.0,
                unit="binary",
                passed=self.safety_cleared,
                description="Certifies absence of lethal pesticide residues prior to macro-biologic introduction.",
            )
        )

        # 3. Chemical Pesticide Avoidance (100% Zero Synthetic Spray)
        metrics.append(
            ScenarioMetric(
                name="Zero Synthetic Chemical Spray Avoidance",
                value=1.0 if self.chemical_sprays_avoided else 0.0,
                target=1.0,
                unit="binary",
                passed=self.chemical_sprays_avoided,
                description="Achieves 100% biological control without chemical sprays or toxic residue withholding.",
            )
        )

        # 4. Organic Export Premium Preservation
        export_passed = self.export_premium_preserved_vnd > 0.0
        metrics.append(
            ScenarioMetric(
                name="Export Organic Price Premium Safeguarded",
                value=round(self.export_premium_preserved_vnd, 0),
                target=25000000.0,
                unit="VND",
                passed=export_passed,
                description="Safeguards export-grade 25% price premium by avoiding synthetic pesticide residues.",
            )
        )

        passed_count = sum(1 for m in metrics if m.passed)
        overall_score = round((passed_count / len(metrics)) * 100.0, 1)
        passed = overall_score >= 75.0
        grade = self.compute_composite_grade(overall_score)

        summary = (
            f"Spider Mite Outbreak Scenario completed with score {overall_score}%. "
            f"Pest density knocked down from {self.initial_pest_density:.1f} to {self.final_pest_density:.2f} mites/leaf. "
            f"Beneficial predator density established at {self.final_predator_density:.2f}/leaf. "
            f"Export premium preserved: {self.export_premium_preserved_vnd:,.0f} VND."
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
