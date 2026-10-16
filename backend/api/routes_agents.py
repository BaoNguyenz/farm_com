"""
Multi-Agent Council & Deliberation Endpoints
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any
from backend.core.twin_state import FarmDigitalTwin

router = APIRouter(prefix="/api/agents", tags=["Agent Swarm"])

def get_farm_instance():
    from backend.main import farm_instance
    return farm_instance

def get_commander_instance():
    from backend.main import commander_agent
    return commander_agent

@router.post("/convene")
async def convene_council(
    farm: FarmDigitalTwin = Depends(get_farm_instance),
    commander = Depends(get_commander_instance)
) -> Dict[str, Any]:
    """
    Trigger immediate meeting of the Farm Multi-Agent Council.
    Each agent evaluates telemetry and the Commander renders a verdict.
    """
    verdict = await commander.convene_council(farm)
    return verdict.to_dict()
