"""
Unit tests for Greenhouse Heat Trapping & Pollination Foraging Cessation Benchmark Scenario.
"""
import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.benchmarks.greenhouse_heat_trap import GreenhouseHeatTrapScenario
from backend.benchmarks.runner import BenchmarkRunner
from backend.core.twin_state import create_default_farm


def test_greenhouse_heat_trap_lifecycle_and_metrics() -> None:
    farm = create_default_farm()
    scenario = GreenhouseHeatTrapScenario()

    # 1. Setup phase: polyhouse closed, ambient heat waves
    asyncio.run(scenario.setup(farm))
    assert farm.current_weather is not None
    assert farm.current_weather.temp_c == 33.5
    assert farm.current_weather.solar_radiation_mj == 24.5

    # 2. Step simulation phase: emergency ventilation & evaporative wet pad cooling
    asyncio.run(scenario.step_scenario(farm, elapsed_hours=1.5))
    assert scenario.final_temp_c <= 28.5
    assert scenario.final_vpd_kpa <= 1.6
    assert scenario.co2_interlock_engaged is True
    assert scenario.foraging_resumed is True

    # 3. Evaluation phase
    verdict_mock = object()
    result = asyncio.run(scenario.evaluate_response(farm, verdict_mock))

    assert result.scenario_id == "scenario_greenhouse_heat_trap"
    assert result.passed is True
    assert result.grade in ("A+", "A")
    assert result.score >= 75.0
    assert len(result.metrics) == 4

    metric_names = [m.name for m in result.metrics]
    assert "Thermal Foraging Temperature Recovery" in metric_names
    assert "Canopy VPD Stress Mitigation" in metric_names
    assert "Anti-Exhaust CO2 Interlock Safety" in metric_names
    assert "Bumblebee Sonication Resumption" in metric_names


def test_greenhouse_heat_trap_runner_execution() -> None:
    runner = BenchmarkRunner()
    farm = create_default_farm()

    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    result = asyncio.run(runner.run_scenario("greenhouse_heat_trap", farm, commander))
    assert result.scenario_id == "scenario_greenhouse_heat_trap"
    assert result.passed is True
    assert result.score >= 75.0
    assert "Greenhouse Heat Trapping Scenario completed" in result.summary
