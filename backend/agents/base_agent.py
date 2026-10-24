"""
Base Agent Interface
Defines the cognitive loop: Perception -> Evaluation -> Deliberation -> Action Recommendation.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import time


class AgentRole(str, Enum):
    AGRONOMIST = "Chief Agronomist & Plant Doctor"
    IRRIGATION = "Hydrological & Irrigation Engineer"
    MARKET = "Agricultural Economics & Market Strategist"
    COMMANDER = "Farm Commander & Council Orchestrator"


class AgentOpinion(BaseModel):
    agent_id: str
    role: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str
    urgency: str = "low"  # "low", "medium", "critical"
    data_points: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    timestamp: float = Field(default_factory=time.time)


class DebateVote(BaseModel):
    agent_id: str
    topic: str = "farm_operations"
    vote_choice: str = "APPROVE"  # "APPROVE", "DEFER", "REJECT", "CONCERNS"
    weight: float = 1.0
    confidence: float = 1.0
    rationale: str = ""

    # Convenience aliases
    @property
    def voter_id(self) -> str:
        return self.agent_id

    @property
    def vote(self) -> str:
        return self.vote_choice.lower()

    @property
    def argument(self) -> str:
        return self.rationale


class DebateRound(BaseModel):
    round_number: int = 1
    topic: str = "farm_operations"
    opinions: List[AgentOpinion] = Field(default_factory=list)
    votes: List[DebateVote] = Field(default_factory=list)
    consensus_choice: Optional[str] = None
    consensus_score: float = 0.0
    consensus_verdict: Optional[str] = None
    weighted_score: Optional[float] = None
    resolution_notes: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None



class BaseFarmAgent(ABC):
    def __init__(self, agent_id: str, role: str, expertise_domain: str = "general"):
        self.agent_id = agent_id
        self.role = role
        self.expertise_domain = expertise_domain

    def get_domain_weight(self, topic: str) -> float:
        """Calculates domain voting weight: specialist agent gets 2.0x weight on their home domain."""
        t = topic.lower()
        if self.expertise_domain in t:
            return 2.0
        # Agronomist covers crop biology and pathology
        if self.expertise_domain in ("agronomy", "pathology") and any(k in t for k in ("agronomy", "pathology", "biology", "crop", "canopy", "plant")):
            return 2.0
        return 1.0


    @abstractmethod
    async def evaluate(self, farm_state: Any) -> AgentOpinion:
        """
        Evaluate current Digital Twin farm state and generate an informed opinion.
        """
        pass

    def vote_on_proposal(self, proposal: Dict[str, Any], context: Dict[str, Any]) -> DebateVote:
        """Synchronous debate vote on an operational proposal."""
        domain = proposal.get("action_domain", "general")
        weight = self.get_domain_weight(domain)
        urgency = proposal.get("urgency", "low")
        return DebateVote(
            agent_id=self.agent_id,
            topic=domain,
            vote_choice="APPROVE",
            weight=weight,
            confidence=0.9 if weight >= 2.0 else 0.8,
            rationale=f"{self.role} approves proposal in domain '{domain}' (urgency: {urgency})."
        )

    async def cast_vote(self, topic: str, proposal: str, farm_state: Any) -> DebateVote:
        """Default voting policy based on urgency and domain expertise."""
        op = await self.evaluate(farm_state)
        weight = self.get_domain_weight(topic)
        choice = "APPROVE" if op.urgency in ("critical", "medium") else "DEFER"
        return DebateVote(
            agent_id=self.agent_id,
            topic=topic,
            vote_choice=choice,
            weight=weight,
            confidence=0.85,
            rationale=f"{self.role} voted {choice} with weight {weight}: {op.recommendation}"
        )



# Alias for standard naming
BaseAgent = BaseFarmAgent
