"""
Unit tests for Multi-Scenario Benchmark Suite Runner (Task 7.1 - 7.3)
Tests batch execution, composite grade scoring, and report serialization.
"""
import asyncio
from backend.benchmarks.runner import BenchmarkRunner, BenchmarkSuiteReport
from backend.core.twin_state import create_default_farm
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent


def test_runner_available_scenarios_catalog():
    runner = BenchmarkRunner()
    scenarios = runner.get_available_scenarios()

    assert len(scenarios) >= 4
    scenario_ids = [s["id"] for s in scenarios]
    assert "scenario_drought_shock" in scenario_ids
    assert "scenario_fungal_outbreak" in scenario_ids
    assert "scenario_tariff_optimization" in scenario_ids
    assert "scenario_frost_hazard" in scenario_ids


def test_runner_run_single_scenario():
    runner = BenchmarkRunner()
    farm = create_default_farm(width=3, height=3)
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    res = asyncio.run(runner.run_scenario("drought_shock", farm, commander))
    assert res.scenario_id == "scenario_drought_shock"
    assert res.score >= 70.0
    assert res.passed is True


def test_runner_run_all_battery_and_grading():
    runner = BenchmarkRunner()
    farm = create_default_farm(width=3, height=3)
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    report = asyncio.run(runner.run_all(farm, commander))

    assert isinstance(report, BenchmarkSuiteReport)
    assert report.total_scenarios == 4
    assert report.passed_scenarios >= 3
    assert report.composite_score >= 70.0
    assert report.composite_grade in ("A+", "A", "B")
    assert len(report.results) == 4

    # Check last_report property
    assert runner.last_report is not None
    assert runner.last_report.composite_score == report.composite_score

    # Check dict export
    d = report.to_dict()
    assert d["total_scenarios"] == 4
    assert "results" in d
    assert len(d["results"]) == 4
