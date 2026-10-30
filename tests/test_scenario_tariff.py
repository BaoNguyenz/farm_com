"""
Unit tests for Electricity Tariff Optimization Benchmark Scenario (Task 7.3)
Tests peak-hour energy deferral, pumping cost minimization, and financial savings evaluation.
"""
import asyncio
from backend.benchmarks.tariff_optimization import TariffOptimizationScenario
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_tariff_optimization_setup_and_stepping():
    farm = create_default_farm(width=3, height=3)
    scenario = TariffOptimizationScenario()

    asyncio.run(scenario.setup(farm))

    assert all(z.soil_moisture_pct == 54.0 for z in farm.zones)
    assert all(z.health_status == "healthy" for z in farm.zones)

    asyncio.run(scenario.step_scenario(farm, elapsed_hours=4.0))
    assert farm.zones[0].soil_moisture_pct < 54.0


def test_tariff_optimization_council_evaluation():
    farm = create_default_farm(width=3, height=3)
    scenario = TariffOptimizationScenario()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    asyncio.run(scenario.setup(farm))
    verdict = asyncio.run(commander.convene_council(farm))

    result = asyncio.run(scenario.evaluate_response(farm, verdict))

    assert result.scenario_id == "scenario_tariff_optimization"
    assert result.score >= 70.0
    assert result.passed is True
    assert result.grade in ("A+", "A", "B")
    assert len(result.metrics) == 3

    # Verify TOU recognition metric
    tou_metric = next(m for m in result.metrics if m.name == "TOU Tariff Window Recognition")
    assert tou_metric.passed is True
