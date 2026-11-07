"""
Unit tests for Grid Blackout & Solar Microgrid Islanding Benchmark Scenario.
"""

import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.grid_blackout import GridBlackoutScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm


def test_grid_blackout_lifecycle_and_metrics():
    farm = create_default_farm()
    scenario = GridBlackoutScenario()

    # Setup phase
    asyncio.run(scenario.setup(farm))
    assert farm.current_weather.temp_c == 32.5
    assert farm.current_weather.humidity_percent == 42.0
    assert farm.zones[0].health_status == "stressed"

    # Step simulation phase
    initial_moisture = farm.zones[0].soil_moisture_pct
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=2.0))
    assert farm.zones[0].soil_moisture_pct < initial_moisture

    # Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_grid_blackout"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 85.0
    assert len(result.metrics) == 3

    # Check metrics
    metric_names = [m.name for m in result.metrics]
    assert "Microgrid Islanding Execution" in metric_names
    assert "Solar Generation Coverage" in metric_names
    assert "Battery Reserve Preservation" in metric_names


def test_grid_blackout_runner_integration():
    farm = create_default_farm()
    agronomist = AgronomistAgent()
    irrigation = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agronomist, irrigation, market)
    runner = BenchmarkRunner()

    result = asyncio.run(runner.run_scenario("grid_blackout", farm, commander))
    assert result.scenario_id == "scenario_grid_blackout"
    assert result.passed is True
    assert result.score >= 80.0
