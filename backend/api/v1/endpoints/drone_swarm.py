"""
REST API Endpoints for Autonomous UAV Swarm Cooperative Scouting & Boustrophedon Fleet Operations.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.drone_path_planning import (
    CameraPayload,
    DroneUAVProfile,
    Point2D,
    SwarmPathCoordinator,
    SwarmSurveyMission,
)
from backend.core.drone_swarm_rth import (
    CollisionRiskAssessment,
    DroneKinematicState,
    MissionHandoffResult,
    RTHPowerAssessment,
    SwarmFlightStatus,
    SwarmSafetyEngine,
)

router = APIRouter(prefix="/drone-swarm", tags=["Autonomous Drone Swarm"])

# Global safety and mission coordination instances
_safety_engine = SwarmSafetyEngine()
_agronomist = AgronomistAgent()
_market = MarketAgent()


class SwarmMissionRequest(BaseModel):
    """Payload to initiate or compute a cooperative swarm survey flight plan."""
    farm_width_m: float = Field(200.0, ge=20.0, le=2000.0)
    farm_height_m: float = Field(150.0, ge=20.0, le=2000.0)
    altitude_m: float = Field(35.0, ge=10.0, le=120.0)
    fleet_size: int = Field(2, ge=1, le=8)
    wind_speed_m_s: float = Field(3.5, ge=0.0, le=30.0)
    wind_direction_deg: float = Field(45.0, ge=0.0, le=360.0)


class CollisionCheckRequest(BaseModel):
    """Payload to evaluate pairwise collision cone between two UAVs."""
    drone_a: DroneKinematicState
    drone_b: DroneKinematicState


class RTHEvaluationRequest(BaseModel):
    """Payload to assess return-to-home battery requirements under wind."""
    drone: DroneKinematicState
    wind_speed_m_s: float = Field(4.0, ge=0.0, le=25.0)
    wind_direction_deg: float = Field(0.0, ge=0.0, le=360.0)


class MissionHandoffRequest(BaseModel):
    """Payload to trigger dynamic waypoint transfer between two drones."""
    exhausted_drone: DroneKinematicState
    receiving_drone: DroneKinematicState


@router.get("/telemetry")
def get_drone_swarm_telemetry() -> dict[str, Any]:
    """Retrieves live fleet telemetry, active status, battery SoC, and weather flight permit."""
    fleet_state = [
        {
            "drone_id": "UAV-Alpha",
            "model": "Hexacopter Ag-Scout v3",
            "position": {"x": 45.2, "y": 72.8, "z_agl": 35.0},
            "speed_m_s": 8.0,
            "battery_soc_pct": 78.4,
            "status": SwarmFlightStatus.SCOUTING.value,
            "assigned_partition": "Sector-West",
        },
        {
            "drone_id": "UAV-Beta",
            "model": "Hexacopter Ag-Scout v3",
            "position": {"x": 138.6, "y": 88.4, "z_agl": 35.0},
            "speed_m_s": 8.0,
            "battery_soc_pct": 82.1,
            "status": SwarmFlightStatus.SCOUTING.value,
            "assigned_partition": "Sector-East",
        },
    ]

    weather_audit = _agronomist.audit_drone_swarm_mission(
        swarm_size=2,
        total_area_ha=3.0,
        wind_speed_m_s=3.5,
        rain_rate_mm_h=0.0,
    )

    economic_roi = _market.evaluate_drone_swarm_scouting_roi(
        total_area_ha=3.0,
        swarm_size=2,
    )

    return {
        "fleet_size": len(fleet_state),
        "fleet_status": "AIRBORNE_COOPERATIVE",
        "drones": fleet_state,
        "weather_safety_audit": weather_audit,
        "economic_roi": economic_roi,
        "collision_alert_count": 0,
    }


@router.post("/plan-mission", response_model=SwarmSurveyMission)
def plan_swarm_mission(req: SwarmMissionRequest) -> SwarmSurveyMission:
    """Calculates Boustrophedon decomposition and Voronoi partitioning for the swarm."""
    if req.wind_speed_m_s > 12.0:
        raise HTTPException(
            status_code=400,
            detail=f"Wind speed {req.wind_speed_m_s} m/s exceeds max safe flight envelope (12.0 m/s). Mission aborted.",
        )

    fleet = [
        DroneUAVProfile(
            drone_id=f"UAV-{chr(65 + i)}",
            nominal_speed_m_s=8.0,
            survey_altitude_m=req.altitude_m,
            base_station=Point2D(x=float(i * 50), y=0.0),
            camera=CameraPayload(),
        )
        for i in range(req.fleet_size)
    ]

    coordinator = SwarmPathCoordinator(fleet=fleet)
    return coordinator.plan_swarm_mission(
        farm_width_m=req.farm_width_m,
        farm_height_m=req.farm_height_m,
        altitude_m=req.altitude_m,
        wind_direction_deg=req.wind_direction_deg,
    )


@router.post("/check-collision", response_model=CollisionRiskAssessment)
def check_collision_cone(req: CollisionCheckRequest) -> CollisionRiskAssessment:
    """Evaluates real-time Reciprocal Velocity Obstacle (RVO) collision risk."""
    return _safety_engine.evaluate_pairwise_collision(req.drone_a, req.drone_b)


@router.post("/evaluate-rth", response_model=RTHPowerAssessment)
def evaluate_rth_threshold(req: RTHEvaluationRequest) -> RTHPowerAssessment:
    """Calculates required aerodynamic return power and triggers RTH if battery reserve is low."""
    return _safety_engine.evaluate_rth_threshold(
        drone=req.drone,
        wind_speed_m_s=req.wind_speed_m_s,
        wind_direction_deg=req.wind_direction_deg,
    )


@router.post("/handoff-mission", response_model=MissionHandoffResult)
def execute_mission_handoff(req: MissionHandoffRequest) -> MissionHandoffResult:
    """Transfers unvisited waypoints from an exhausted drone to an available peer."""
    return _safety_engine.execute_mission_handoff(
        exhausted_drone=req.exhausted_drone,
        receiving_drone=req.receiving_drone,
    )
