"""
Base Framework for Autonomous Farm Scenario Benchmarks (Task 7.1 - 7.3)
Defines benchmark lifecycle, evaluation metrics, and scoring interfaces.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import time
from backend.core.twin_state import FarmDigitalTwin


class ScenarioMetric(BaseModel):
    """Individual benchmark quantitative metric."""
    name: str
    value: float
    target: float
    unit: str
    passed: bool
    weight: float = 1.0
    notes: str = ""


class ScenarioEvaluationResult(BaseModel):
    """Consolidated outcome of an executed scenario benchmark."""
    scenario_id: str
    scenario_name: str
    score: float = Field(ge=0.0, le=100.0)
    passed: bool
    grade: str  # A+, A, B, C, F
    metrics: List[ScenarioMetric] = Field(default_factory=list)
    summary: str
    elapsed_time_s: float = 0.0
    timestamp: float = Field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BaseScenarioBenchmark(ABC):
    """
    Abstract Base Class for Farm Stress and Resilience Scenarios.
    Lifecycle:
    1. setup(farm) -> Inject initial environmental stress or anomaly conditions.
    2. step_scenario(farm, elapsed_hours) -> Advance physical processes.
    3. evaluate_response(farm, verdict) -> Measure multi-agent response efficiency.
    """
    def __init__(self, scenario_id: str, scenario_name: str, description: str, duration_hours: float = 24.0):
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.description = description
        self.duration_hours = duration_hours

    @abstractmethod
    async def setup(self, farm: FarmDigitalTwin) -> None:
        """Configures farm digital twin with scenario conditions."""
        pass

    @abstractmethod
    async def step_scenario(self, farm: FarmDigitalTwin, elapsed_hours: float) -> None:
        """Simulates physical time steps and updates crop/weather dynamics."""
        pass

    @abstractmethod
    async def evaluate_response(self, farm: FarmDigitalTwin, verdict: Any) -> ScenarioEvaluationResult:
        """Evaluates whether agent decisions averted risk and met biological targets."""
        pass

    def compute_composite_grade(self, score: float) -> str:
        """Calculates standard letter grade based on percentage score."""
        if score >= 90.0:
            return "A+"
        elif score >= 80.0:
            return "A"
        elif score >= 70.0:
            return "B"
        elif score >= 60.0:
            return "C"
        return "F"
