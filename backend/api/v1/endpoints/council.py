"""
Multi-Agent Council & Consensus Debate Endpoints (v1)
Provides endpoints for triggering multi-agent deliberation, custom proposal arbitration, and historical verdicts.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from backend.core.twin_state import FarmDigitalTwin
from backend.agents.commander import CommanderAgent, FarmCouncilVerdict


router = APIRouter(prefix="/council", tags=["Agent Council v1"])

# In-memory history of council verdicts
_council_history: List[Dict[str, Any]] = []


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


def get_commander() -> CommanderAgent:
    from backend.main import commander_agent
    return commander_agent


class ProposalDebateRequest(BaseModel):
    action_type: str = Field(..., description="Action identifier (e.g. irrigate_plot_zones, apply_fungicide)")
    action_domain: str = Field("general", description="Expertise domain: hydrology, agronomy, pathology, economics")
    urgency: str = Field("medium", description="Urgency rating: low, medium, critical")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary operational parameters")


@router.post("/convene")
async def convene_council(
    farm: FarmDigitalTwin = Depends(get_farm_state),
    commander: CommanderAgent = Depends(get_commander)
) -> Dict[str, Any]:
    """Trigger an autonomous session of the Farm Council. All specialist agents evaluate state and debate."""
    from backend.api.v1.endpoints.audit import _global_dispatcher
    verdict: FarmCouncilVerdict = await commander.convene_council(farm, dispatcher=_global_dispatcher)
    verdict_dict = verdict.to_dict()


    # Append to in-memory history (keep latest 50)
    _council_history.append(verdict_dict)
    if len(_council_history) > 50:
        _council_history.pop(0)

    # Broadcast to WebSocket subscribers
    from backend.core.websocket_manager import ws_hub
    await ws_hub.broadcast_council_event("COUNCIL_CONCLUDED", verdict_dict)


    return verdict_dict


@router.post("/debate")
async def arbitrate_custom_proposal(
    proposal: ProposalDebateRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state),
    commander: CommanderAgent = Depends(get_commander)
) -> Dict[str, Any]:
    """Submit a custom operational proposal for formal council debate with domain expertise weighting."""
    from backend.agents.market import MarketAgent
    market: MarketAgent = commander.market

    tariff_info = market.get_electricity_tariff()
    context = {
        "tariff_tier": tariff_info.get("tier", "normal"),
        "weather": farm.current_weather.model_dump(),
        "zones_count": len(farm.zones)
    }

    debate_round = commander.arbitrate_debate(proposal.model_dump(), context)
    return debate_round.model_dump()


@router.get("/history")
async def get_council_history() -> List[Dict[str, Any]]:
    """Retrieve historical record of council sessions and debate outcomes."""
    return _council_history
