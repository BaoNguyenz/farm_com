"""
Unit tests for Sudden Weed Outbreak & Autonomous Rover Swarm Benchmark Scenario.
"""
import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.runner import BenchmarkRunner
from backend.benchmarks.weed_rover_mission import WeedOutbreakRoverMissionScenario
from backend.core.twin_state import create_default_farm


def test_weed_rover_scenario_lifecycle_and_metrics() -> None:
    farm = create_default_farm()
    scenario = WeedOutbreakRoverMissionScenario()

    # Setup phase
    asyncio.run(scenario.setup(farm))
    zone_0 = farm.get_zone("Z_0_0")
    assert zone_0 is not None
    assert zone_0.health_status == "weed_infested"
    assert zone_0.soil_moisture_pct == 82.0

    # Step simulation phase (advance rover patrol for 2 hours)
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=2.0))

    # Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_weed_rover_mission"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 80.0
    assert len(result.metrics) == 3


def test_weed_rover_runner_execution() -> None:
    runner = BenchmarkRunner()
    farm = create_default_farm()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    result = asyncio.run(runner.run_scenario("weed_rover_mission", farm, commander))
    assert result.scenario_id == "scenario_weed_rover_mission"
    assert result.passed is True
    assert result.score >= 75.0
    assert "Weed Outbreak Rover Benchmark completed" in result.summary
