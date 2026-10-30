"""
Agricultural Scenario Benchmarks Package (Task 7.1 - 7.3)
"""
from backend.benchmarks.base import (
    BaseScenarioBenchmark,
    ScenarioMetric,
    ScenarioEvaluationResult,
)
from backend.benchmarks.drought_shock import DroughtShockScenario
from backend.benchmarks.fungal_outbreak import FungalOutbreakScenario
from backend.benchmarks.tariff_optimization import TariffOptimizationScenario
from backend.benchmarks.frost_hazard import FrostHazardScenario
from backend.benchmarks.runner import (
    BenchmarkRunner,
    BenchmarkSuiteReport,
    benchmark_runner,
)

__all__ = [
    "BaseScenarioBenchmark",
    "ScenarioMetric",
    "ScenarioEvaluationResult",
    "DroughtShockScenario",
    "FungalOutbreakScenario",
    "TariffOptimizationScenario",
    "FrostHazardScenario",
    "BenchmarkRunner",
    "BenchmarkSuiteReport",
    "benchmark_runner",
]
