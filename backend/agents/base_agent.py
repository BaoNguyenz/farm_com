"""
Base Agent Interface
Defines the cognitive loop: Perception -> Evaluation -> Deliberation -> Action Recommendation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel
import time

class AgentOpinion(BaseModel):
    agent_id: str
    role: str
    confidence: float # 0.0 to 1.0
    recommendation: str
    urgency: str # "low", "medium", "critical"
    data_points: Dict[str, Any]
    reasoning: str
    timestamp: float = time.time()

class BaseFarmAgent(ABC):
    def __init__(self, agent_id: str, role: str):
        self.agent_id = agent_id
        self.role = role

    @abstractmethod
    async def evaluate(self, farm_state: Any) -> AgentOpinion:
        """
        Evaluate current Digital Twin farm state and generate an informed opinion.
        """
        pass

# Alias for standard naming
BaseAgent = BaseFarmAgent
