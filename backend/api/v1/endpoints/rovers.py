"""
Autonomous Farm Rover Swarm Fleet Telemetry & Mission Control REST Endpoints.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.farm_rover import RoverState
from backend.core.rover_fleet import (
    FleetMission,
    FleetStatusReport,
    RoverFleetCoordinator,
)

router = APIRouter(prefix="/rovers", tags=["rovers"])
fleet_coordinator = RoverFleetCoordinator()


class MissionDispatchRequest(BaseModel):
    plot_id: str = Field(..., description="Target plot identifier (e.g. Z_0_1)")
    row_index: int = Field(1, ge=1, le=8, description="Furrow row index")
    priority: str = Field("routine_patrol", description="Mission urgency (routine_patrol / urgent_infestation)")


class FleetCycleSimulationRequest(BaseModel):
    duration_seconds: float = Field(60.0, ge=1.0, le=3600.0)
    soil_moisture_pct: float = Field(55.0, ge=10.0, le=100.0)


@router.get("/telemetry", response_model=FleetStatusReport)
def get_fleet_telemetry() -> FleetStatusReport:
    """
    Returns real-time status, battery SoC, weeding totals, and GPS coordinates for all rovers.
    """
    return fleet_coordinator.get_fleet_status()


@router.get("/{rover_id}", response_model=RoverState)
def get_single_rover_telemetry(rover_id: str) -> RoverState:
    """
    Returns granular hardware status, wheel slip, and battery health for a specific rover.
    """
    rover = fleet_coordinator.rovers.get(rover_id)
    if not rover:
        raise HTTPException(status_code=404, detail=f"Rover '{rover_id}' not found in fleet roster")
    return rover.state


@router.post("/dispatch", response_model=FleetMission)
def dispatch_rover_mission(payload: MissionDispatchRequest) -> FleetMission:
    """
    Commands an autonomous ground rover to execute zero-chemical mechanical weeding on a plot furrow.
    """
    try:
        return fleet_coordinator.dispatch_mission(
            plot_id=payload.plot_id,
            row_index=payload.row_index,
            priority=payload.priority,
        )
    except RuntimeError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/recall")
def recall_fleet_to_dock() -> dict[str, Any]:
    """
    Triggers emergency return-to-base and docking for all rovers across the farm.
    """
    recalled_states = fleet_coordinator.recall_all_to_dock()
    return {
        "status": "success",
        "action": "fleet_recall",
        "recalled_count": len(recalled_states),
        "fleet": [s.model_dump() for s in recalled_states],
    }


@router.post("/cycle", response_model=FleetStatusReport)
def simulate_fleet_cycle(payload: FleetCycleSimulationRequest) -> FleetStatusReport:
    """
    Advances physical kinematics, weeding strikes, and battery consumption for all active rovers.
    """
    return fleet_coordinator.step_fleet_cycle(
        duration_seconds=payload.duration_seconds,
        soil_moisture_pct=payload.soil_moisture_pct,
    )
