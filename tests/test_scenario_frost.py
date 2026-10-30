"""
Unit tests for Cold Frost & Radiative Inversion Scenario (Task 7.1 - 7.3)
Tests low-temperature hazard detection, radiative cooling stepping, and freeze prevention scoring.
"""
import asyncio
from backend.benchmarks.frost_hazard import FrostHazardScenario
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_frost_hazard_setup_and_stepping():
    farm = create_default_farm(width=3, height=3)
    scenario = FrostHazardScenario()

    asyncio.run(scenario.setup(farm))

    assert farm.current_weather.temp_c == 2.2
    assert farm.current_weather.temp_min == 1.0
    assert all(z.soil_temp_c == 4.5 for z in farm.zones)

    asyncio.run(scenario.step_scenario(farm, elapsed_hours=6.0))
    # Prolonged cold should chill soil temperatures
    assert farm.zones[0].soil_temp_c < 4.5
    assert any(z.health_status == "frost_risk" for z in farm.zones)


def test_frost_hazard_council_evaluation():
    farm = create_default_farm(width=3, height=3)
    scenario = FrostHazardScenario()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    asyncio.run(scenario.setup(farm))
    verdict = asyncio.run(commander.convene_council(farm))

    result = asyncio.run(scenario.evaluate_response(farm, verdict))

    assert result.scenario_id == "scenario_frost_hazard"
    assert result.score >= 70.0
    assert result.passed is True
    assert result.grade in ("A+", "A", "B")
    assert len(result.metrics) == 3

    frost_metric = next(m for m in result.metrics if m.name == "Nocturnal Frost Hazard Detection")
    assert frost_metric.passed is True
