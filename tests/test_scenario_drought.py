"""
Unit tests for Drought Shock Benchmark Scenario (Task 7.1)
Tests acute evapotranspiration deficit simulation, emergency detection, and wilting prevention scoring.
"""
import asyncio
from backend.benchmarks.drought_shock import DroughtShockScenario
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_drought_shock_setup_and_stepping():
    farm = create_default_farm(width=3, height=3)
    scenario = DroughtShockScenario()

    asyncio.run(scenario.setup(farm))

    assert farm.current_weather.temp_c == 39.5
    assert farm.current_weather.humidity_percent == 20.0
    assert any(z.health_status == "water_stressed" for z in farm.zones)

    initial_moist = farm.zones[0].soil_moisture_pct
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=4.0))

    # Stepping without water should decrease soil moisture
    assert farm.zones[0].soil_moisture_pct < initial_moist


def test_drought_shock_council_evaluation():
    farm = create_default_farm(width=3, height=3)
    scenario = DroughtShockScenario()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    asyncio.run(scenario.setup(farm))
    verdict = asyncio.run(commander.convene_council(farm))

    result = asyncio.run(scenario.evaluate_response(farm, verdict))

    assert result.scenario_id == "scenario_drought_shock"
    assert result.score >= 70.0
    assert result.passed is True
    assert result.grade in ("A+", "A", "B")
    assert len(result.metrics) == 3

    # Ensure emergency detection passed
    emergency_metric = next(m for m in result.metrics if m.name == "Emergency Urgency Detection")
    assert emergency_metric.passed is True
