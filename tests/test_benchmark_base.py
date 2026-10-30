"""
Unit tests for Scenario Benchmark Base Framework (Task 7.1 - 7.3)
Tests metric tracking, result serialization, and benchmark grade computation.
"""
import asyncio
from backend.benchmarks.base import ScenarioMetric, ScenarioEvaluationResult, BaseScenarioBenchmark
from backend.core.twin_state import create_default_farm


class DummyTestScenario(BaseScenarioBenchmark):
    def __init__(self):
        super().__init__(
            scenario_id="dummy_scenario",
            scenario_name="Dummy Test Scenario",
            description="Tests the base scenario evaluation pipeline.",
            duration_hours=12.0
        )

    async def setup(self, farm):
        farm.current_weather.temp_c = 25.0

    async def step_scenario(self, farm, elapsed_hours):
        pass

    async def evaluate_response(self, farm, verdict):
        metric = ScenarioMetric(
            name="Test Metric",
            value=85.0,
            target=80.0,
            unit="%",
            passed=True,
            weight=1.0
        )
        return ScenarioEvaluationResult(
            scenario_id=self.scenario_id,
            scenario_name=self.scenario_name,
            score=85.0,
            passed=True,
            grade=self.compute_composite_grade(85.0),
            metrics=[metric],
            summary="Test passed successfully"
        )


def test_scenario_metric_model():
    metric = ScenarioMetric(
        name="Soil Moisture Retention",
        value=42.5,
        target=35.0,
        unit="%",
        passed=True,
        weight=1.5,
        notes="Maintained above wilting point"
    )
    assert metric.name == "Soil Moisture Retention"
    assert metric.value == 42.5
    assert metric.passed is True
    assert metric.weight == 1.5


def test_scenario_grade_computation():
    scenario = DummyTestScenario()
    assert scenario.compute_composite_grade(95.0) == "A+"
    assert scenario.compute_composite_grade(90.0) == "A+"
    assert scenario.compute_composite_grade(85.0) == "A"
    assert scenario.compute_composite_grade(75.0) == "B"
    assert scenario.compute_composite_grade(65.0) == "C"
    assert scenario.compute_composite_grade(45.0) == "F"


def test_scenario_lifecycle():
    farm = create_default_farm(width=3, height=3)
    scenario = DummyTestScenario()

    assert scenario.scenario_id == "dummy_scenario"
    assert scenario.duration_hours == 12.0

    asyncio.run(scenario.setup(farm))
    assert farm.current_weather.temp_c == 25.0

    asyncio.run(scenario.step_scenario(farm, 12.0))
    res = asyncio.run(scenario.evaluate_response(farm, None))

    assert isinstance(res, ScenarioEvaluationResult)
    assert res.score == 85.0
    assert res.grade == "A"
    assert res.passed is True
    assert len(res.metrics) == 1

    d = res.to_dict()
    assert d["scenario_id"] == "dummy_scenario"
    assert "metrics" in d
    assert d["metrics"][0]["name"] == "Test Metric"
