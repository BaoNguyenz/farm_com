"""
Unit tests for Nitrate Leaching and Root Hypoxia Flash Flood Benchmark Scenario.
"""
import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.leaching_flood import NitrateLeachingFloodScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm


def test_leaching_flood_lifecycle_and_metrics() -> None:
    farm = create_default_farm()
    scenario = NitrateLeachingFloodScenario()

    # Setup phase
    asyncio.run(scenario.setup(farm))
    assert farm.current_weather.precipitation_mm == 75.0
    assert farm.zones[0].soil_moisture_pct == 94.0
    assert farm.zones[0].health_status == "waterlogged"

    # Step simulation phase (drainage over 3 hours)
    initial_moisture = farm.zones[0].soil_moisture_pct
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=3.0))
    assert farm.zones[0].soil_moisture_pct < initial_moisture

    # Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_leaching_flood"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 80.0
    assert len(result.metrics) == 3


def test_leaching_flood_runner_execution() -> None:
    runner = BenchmarkRunner()
    farm = create_default_farm()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    result = asyncio.run(runner.run_scenario("leaching_flood", farm, commander))
    assert result.scenario_id == "scenario_leaching_flood"
    assert result.passed is True
    assert result.score >= 75.0
    assert "Flood Benchmark completed" in result.summary
