"""
Multi-Scenario Benchmark Suite Runner
Executes batch scenarios, aggregates performance metrics, and calculates composite agro-resilience grades.
"""
import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from backend.benchmarks.base import BaseScenarioBenchmark, ScenarioEvaluationResult
from backend.benchmarks.drought_shock import DroughtShockScenario
from backend.benchmarks.fungal_outbreak import FungalOutbreakScenario
from backend.benchmarks.tariff_optimization import TariffOptimizationScenario
from backend.benchmarks.frost_hazard import FrostHazardScenario
from backend.core.twin_state import FarmDigitalTwin


class BenchmarkSuiteReport(BaseModel):
    """Overall multi-scenario benchmark evaluation report."""
    total_scenarios: int
    passed_scenarios: int
    composite_score: float = Field(ge=0.0, le=100.0)
    composite_grade: str
    results: List[ScenarioEvaluationResult] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BenchmarkRunner:
    """
    Orchestrates execution of agricultural stress and resilience benchmarks.
    """
    def __init__(self):
        self._scenarios: Dict[str, BaseScenarioBenchmark] = {
            "drought_shock": DroughtShockScenario(),
            "fungal_outbreak": FungalOutbreakScenario(),
            "tariff_optimization": TariffOptimizationScenario(),
            "frost_hazard": FrostHazardScenario()
        }
        self._last_report: Optional[BenchmarkSuiteReport] = None

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered scenarios."""
        return [
            {
                "id": s.scenario_id,
                "name": s.scenario_name,
                "description": s.description,
                "duration_hours": s.duration_hours
            }
            for s in self._scenarios.values()
        ]

    async def run_scenario(
        self,
        scenario_key: str,
        farm: FarmDigitalTwin,
        commander: Any
    ) -> ScenarioEvaluationResult:
        """Runs a single scenario end-to-end against the farm digital twin and council."""
        # Find scenario by key or ID
        scenario = self._scenarios.get(scenario_key)
        if not scenario:
            for s in self._scenarios.values():
                if s.scenario_id == scenario_key:
                    scenario = s
                    break

        if not scenario:
            raise ValueError(f"Scenario '{scenario_key}' not found in registered benchmarks.")

        # 1. Setup scenario
        await scenario.setup(farm)

        # 2. Convene council to deliberate under stress
        verdict = await commander.convene_council(farm)

        # 3. Step physics/biology
        await scenario.step_scenario(farm, elapsed_hours=scenario.duration_hours)

        # 4. Evaluate agent response
        result = await scenario.evaluate_response(farm, verdict)
        return result

    async def run_all(
        self,
        farm: FarmDigitalTwin,
        commander: Any
    ) -> BenchmarkSuiteReport:
        """Executes all registered scenarios sequentially and produces a composite scorecard."""
        results: List[ScenarioEvaluationResult] = []

        for key in self._scenarios.keys():
            res = await self.run_scenario(key, farm, commander)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_score = round(sum(r.score for r in results) / max(1, total), 1)

        if avg_score >= 90.0:
            grade = "A+"
        elif avg_score >= 80.0:
            grade = "A"
        elif avg_score >= 70.0:
            grade = "B"
        elif avg_score >= 60.0:
            grade = "C"
        else:
            grade = "F"

        report = BenchmarkSuiteReport(
            total_scenarios=total,
            passed_scenarios=passed,
            composite_score=avg_score,
            composite_grade=grade,
            results=results
        )
        self._last_report = report
        return report

    @property
    def last_report(self) -> Optional[BenchmarkSuiteReport]:
        return self._last_report


# Singleton runner instance
benchmark_runner = BenchmarkRunner()
