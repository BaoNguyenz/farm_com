"""
Unit tests for Spider Mite Outbreak and Macro-Biologic Suppression Benchmark Scenario.
"""
import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.biocontrol_outbreak import SpiderMiteOutbreakScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm


def test_spider_mite_outbreak_lifecycle_and_metrics() -> None:
    """Verify lifecycle of Spider Mite Outbreak benchmark."""
    farm = create_default_farm()
    scenario = SpiderMiteOutbreakScenario()

    # 1. Setup phase: outbreak conditions
    asyncio.run(scenario.setup(farm))
    assert farm.current_weather is not None
    assert farm.current_weather.temp_c == 25.5

    # 2. Step simulation phase: predatory mite introduction & predation kinetics
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=240.0))
    assert scenario.safety_cleared is True
    assert scenario.packages_dispatched >= 8
    assert scenario.final_pest_density <= 5.0  # Knocked down below ET
    assert scenario.export_premium_preserved_vnd > 0.0

    # 3. Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_spider_mite_outbreak"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 75.0
    assert len(result.metrics) == 4

    metric_names = [m.name for m in result.metrics]
    assert "Economic Threshold Pest Suppression" in metric_names
    assert "Canopy Toxic Residue Clearance" in metric_names
    assert "Zero Synthetic Chemical Spray Avoidance" in metric_names
    assert "Export Organic Price Premium Safeguarded" in metric_names


def test_spider_mite_outbreak_runner_execution() -> None:
    """Verify BenchmarkRunner executes biocontrol_outbreak scenario."""
    runner = BenchmarkRunner()
    farm = create_default_farm()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    result = asyncio.run(runner.run_scenario("biocontrol_outbreak", farm, commander))
    assert result.scenario_id == "scenario_spider_mite_outbreak"
    assert result.passed is True
    assert result.score >= 75.0
    assert "Spider Mite Outbreak Scenario completed" in result.summary
