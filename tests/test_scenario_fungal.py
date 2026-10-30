"""
Unit tests for Fungal Outbreak Risk Benchmark Scenario (Task 7.2)
Tests saturation microclimate modeling, spore germination progression, and pathology response scoring.
"""
import asyncio
from backend.benchmarks.fungal_outbreak import FungalOutbreakScenario
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_fungal_outbreak_setup_and_stepping():
    farm = create_default_farm(width=3, height=3)
    scenario = FungalOutbreakScenario()

    asyncio.run(scenario.setup(farm))

    assert farm.current_weather.humidity_percent == 94.0
    assert farm.current_weather.precipitation_mm == 25.0
    assert all(z.soil_moisture_pct > 80.0 for z in farm.zones)

    asyncio.run(scenario.step_scenario(farm, elapsed_hours=6.0))
    # Zones under high moisture and temperature window should reflect spore hazard
    assert any(z.health_status == "fungal_spore_hazard" for z in farm.zones)


def test_fungal_outbreak_council_evaluation():
    farm = create_default_farm(width=3, height=3)
    scenario = FungalOutbreakScenario()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    asyncio.run(scenario.setup(farm))
    verdict = asyncio.run(commander.convene_council(farm))

    result = asyncio.run(scenario.evaluate_response(farm, verdict))

    assert result.scenario_id == "scenario_fungal_outbreak"
    assert result.score >= 70.0
    assert result.passed is True
    assert len(result.metrics) == 3

    # Ensure saturation irrigation suspension passed (no unnecessary watering during flood/saturation)
    suspension_metric = next(m for m in result.metrics if m.name == "Saturation Irrigation Suspension")
    assert suspension_metric.passed is True
