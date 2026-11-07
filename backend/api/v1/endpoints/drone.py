"""
RESTful Endpoints for Autonomous Aerial Drone Scouting & UAV Computer Vision Surveys.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.drone_scouting import DroneScoutingEngine, DroneScoutingReport
from backend.core.twin_state import create_default_farm

router = APIRouter(prefix="/drone", tags=["Drone Scouting & UAV Computer Vision"])

_engine = DroneScoutingEngine()
_default_farm = create_default_farm()
_latest_survey: DroneScoutingReport | None = None


class DroneFlightRequest(BaseModel):
    """Payload to trigger an autonomous UAV scouting sortie."""
    mission_id: str = Field("UAV-AUTO-01", description="Unique flight mission identifier")
    altitude_m: float = Field(30.0, ge=10.0, le=120.0, description="Flight altitude Above Ground Level (AGL) in meters")
    initial_battery_pct: float = Field(95.0, ge=10.0, le=100.0, description="UAV battery charge at takeoff")
    zone_ids: list[str] | None = Field(None, description="Optional target subset of zone IDs to survey")


@router.post("/simulate-flight", response_model=DroneScoutingReport)
def simulate_drone_flight(req: DroneFlightRequest) -> DroneScoutingReport:
    """
    Simulate an autonomous UAV survey flight over target farm plot zones.
    """
    global _latest_survey
    target_zones = _default_farm.zones
    if req.zone_ids:
        target_zones = [z for z in _default_farm.zones if z.id in req.zone_ids]
        if not target_zones:
            target_zones = _default_farm.zones

    report = _engine.simulate_mission(
        zones=target_zones,
        mission_id=req.mission_id,
        altitude_m=req.altitude_m,
        initial_battery_pct=req.initial_battery_pct,
    )
    _latest_survey = report
    return report


@router.get("/surveys/latest", response_model=DroneScoutingReport)
def get_latest_drone_survey() -> DroneScoutingReport:
    """
    Retrieve the most recent completed drone orthomosaic scouting report.
    """
    global _latest_survey
    if _latest_survey is None:
        _latest_survey = _engine.simulate_mission(zones=_default_farm.zones, mission_id="UAV-INIT-00")
    return _latest_survey


@router.get("/anomalies")
def get_drone_anomalies() -> dict[str, Any]:
    """
    Extract high-priority biophysical crop stress anomalies from the latest UAV survey.
    """
    latest = get_latest_drone_survey()
    hotspots = []
    for s in latest.zone_surveys:
        if s.chlorosis_hotspots > 0 or s.emergence_gap_count > 0 or s.weed_pressure_score > 0.40:
            hotspots.append({
                "zone_id": s.zone_id,
                "crop_type": s.crop_type,
                "chlorosis_hotspots": s.chlorosis_hotspots,
                "emergence_gaps": s.emergence_gap_count,
                "weed_pressure_score": s.weed_pressure_score,
                "scouting_urgency": s.scouting_urgency,
                "finding": s.actionable_finding,
            })

    return {
        "mission_id": latest.mission_id,
        "flight_timestamp_utc": latest.timestamp_utc,
        "total_anomalies_count": len(hotspots),
        "critical_count": len(latest.critical_anomalies),
        "anomalous_zones": hotspots,
    }
