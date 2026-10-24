"""
Unit tests for Multi-Agent Council & Debate Protocol (Task 4.1 & Task 4.5)
Validates structured debate rounds, domain expertise weighting, conflict resolution,
and automated action dispatching.
"""
import asyncio
import pytest
from backend.agents.base_agent import AgentRole, DebateVote
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent, FarmCouncilVerdict
from backend.core.twin_state import create_default_farm
from backend.core.dispatcher import ActionDispatcher


@pytest.fixture
def farm():
    return create_default_farm(width=3, height=3)


@pytest.fixture
def council():
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    mark = MarketAgent()
    commander = CommanderAgent(agro, irri, mark)
    return {
        "commander": commander,
        "agro": agro,
        "irri": irri,
        "mark": mark
    }


def test_agent_roles_and_domain_weighting(council):
    agro = council["agro"]
    irri = council["irri"]
    mark = council["mark"]

    assert agro.role == AgentRole.AGRONOMIST.value
    assert irri.role == AgentRole.IRRIGATION.value
    assert mark.role == AgentRole.MARKET.value

    # Specialist agents receive 2.0x weight on their domain of expertise
    assert agro.get_domain_weight("pathology") == 2.0
    assert agro.get_domain_weight("hydrology") == 1.0
    assert agro.get_domain_weight("economics") == 1.0

    assert irri.get_domain_weight("hydrology") == 2.0
    assert irri.get_domain_weight("pathology") == 1.0
    assert irri.get_domain_weight("economics") == 1.0

    assert mark.get_domain_weight("economics") == 2.0
    assert mark.get_domain_weight("hydrology") == 1.0
    assert mark.get_domain_weight("pathology") == 1.0


def test_arbitrate_debate_consensus_approval(council):
    commander = council["commander"]

    proposal = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "medium",
        "zones_count": 2,
        "total_liters": 500.0
    }
    context = {"tariff_tier": "normal"}

    debate = commander.arbitrate_debate(proposal, context)
    assert debate.round_number == 1
    assert debate.consensus_verdict == "approved"
    assert debate.weighted_score > 0.4
    assert len(debate.votes) == 3
    assert all(isinstance(v, DebateVote) for v in debate.votes)


def test_arbitrate_debate_peak_tariff_rejection(council):
    commander = council["commander"]

    # Low-urgency irrigation proposed during PEAK tariff
    proposal = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "low",
        "zones_count": 1,
        "total_liters": 200.0
    }
    context = {"tariff_tier": "peak"}

    # Market should vote reject during peak tariff
    mark_vote = council["mark"].vote_on_proposal(proposal, context)
    assert mark_vote.vote == "reject"
    assert "PEAK" in mark_vote.argument

    debate = commander.arbitrate_debate(proposal, context)
    assert any(v.vote == "reject" for v in debate.votes)


def test_emergency_biological_preservation_override(council):
    commander = council["commander"]

    # Critical wilting proposal during peak tariff
    emergency_proposal = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "critical",
        "emergency_wilting": True,
        "zones_count": 3
    }
    context = {"tariff_tier": "peak"}

    # Market agent accepts emergency actions even during peak hours
    mark_vote = council["mark"].vote_on_proposal(emergency_proposal, context)
    assert mark_vote.vote in ("accept", "approve")

    debate = commander.arbitrate_debate(emergency_proposal, context)
    assert debate.consensus_verdict == "approved"


def test_convene_council_full_pipeline(farm, council):
    commander = council["commander"]
    dispatcher = ActionDispatcher()

    # Pre-condition: Z_2_1 has low moisture
    parched_zone = farm.get_zone("Z_2_1")
    parched_zone.soil_moisture_pct = 32.0  # Under 35% triggers emergency wilting
    parched_zone.health_status = "water_stressed"

    verdict = asyncio.run(commander.convene_council(farm, dispatcher=dispatcher))

    assert isinstance(verdict, FarmCouncilVerdict)
    assert len(verdict.opinions) == 3
    assert len(verdict.debate_rounds) >= 1
    assert len(verdict.scheduled_actions) > 0

    # Verify dispatcher received queued actions
    assert len(dispatcher.action_queue) > 0

    # Verify execution of queued actions
    receipts = dispatcher.execute_pending(farm)
    assert len(receipts) > 0
    assert receipts[-1].entry_index == len(receipts)


    # Verify twin state recovery
    assert parched_zone.soil_moisture_pct > 32.0
    assert parched_zone.health_status == "recovering"

    # Verify verdict dict serialization
    verdict_dict = verdict.to_dict()
    assert "timestamp" in verdict_dict
    assert "executive_summary" in verdict_dict
    assert "opinions" in verdict_dict
    assert "debate_rounds" in verdict_dict
    assert len(verdict_dict["opinions"]) == 3
