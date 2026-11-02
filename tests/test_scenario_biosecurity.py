"""
Unit tests for Task 7.6 Biosecurity Hazard Benchmark Scenario.
Validates multi-pathogen setup, fungal progression, council biosecurity evaluation,
and registration in the BenchmarkRunner suite.
"""

import asyncio
from backend.benchmarks.biosecurity_hazard import BiosecurityHazardScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_biosecurity_hazard_scenario_setup():
    farm = create_default_farm(width=3, height=3)
    scenario = BiosecurityHazardScenario()

    asyncio.run(scenario.setup(farm))

    assert farm.current_weather.temp_c == 21.0
    assert farm.current_weather.humidity_percent == 93.5
    assert all(z.soil_moisture_pct == 87.5 for z in farm.zones)
    assert all(z.health_status == "pathogen_risk" for z in farm.zones)


def test_biosecurity_hazard_scenario_step():
    farm = create_default_farm(width=2, height=2)
    scenario = BiosecurityHazardScenario()

    asyncio.run(scenario.setup(farm))
    initial_ndvi = farm.zones[0].ndvi

    asyncio.run(scenario.step_scenario(farm, elapsed_hours=24.0))
    assert farm.zones[0].ndvi < initial_ndvi


def test_biosecurity_hazard_council_evaluation():
    farm = create_default_farm(width=3, height=3)
    scenario = BiosecurityHazardScenario()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    asyncio.run(scenario.setup(farm))
    verdict = asyncio.run(commander.convene_council(farm))

    result = asyncio.run(scenario.evaluate_response(farm, verdict))

    assert result.scenario_id == "scenario_biosecurity_hazard"
    assert result.score >= 70.0
    assert result.passed is True
    assert result.grade in ("A+", "A", "B")
    assert len(result.metrics) == 3

    veto_metric = next(m for m in result.metrics if m.name == "Biosecurity Waterlogging Veto")
    assert veto_metric.passed is True


def test_biosecurity_scenario_in_benchmark_runner():
    runner = BenchmarkRunner()
    scenarios = runner.get_available_scenarios()
    scenario_ids = [s["id"] for s in scenarios]
    assert "scenario_biosecurity_hazard" in scenario_ids
