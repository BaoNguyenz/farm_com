"""
Unit tests for Cold-Chain Chiller Malfunction & Thermal Abuse Benchmark Scenario.
"""
import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.coldchain_failure import ColdChainChillerFailureScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm


def test_coldchain_failure_lifecycle_and_metrics() -> None:
    farm = create_default_farm()
    scenario = ColdChainChillerFailureScenario()

    # Setup phase
    asyncio.run(scenario.setup(farm))
    chamber_a1 = scenario.cold_engine.chambers["CHAMBER-A1"]
    assert chamber_a1.compressor_active is False
    assert chamber_a1.air_temp_c == 17.5
    assert chamber_a1.ethylene_ppm == 0.28

    # Step simulation phase (thermal aging over 4 hours)
    initial_hours = chamber_a1.hours_in_storage
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=4.0))
    assert chamber_a1.hours_in_storage == initial_hours + 4.0
    assert chamber_a1.ethylene_ppm > 0.28

    # Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_coldchain_failure"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 80.0
    assert len(result.metrics) == 3


def test_coldchain_failure_runner_execution() -> None:
    runner = BenchmarkRunner()
    farm = create_default_farm()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    result = asyncio.run(runner.run_scenario("coldchain_failure", farm, commander))
    assert result.scenario_id == "scenario_coldchain_failure"
    assert result.passed is True
    assert result.score >= 75.0
    assert "Cold-Chain Failure Benchmark completed" in result.summary
