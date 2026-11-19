"""
RESTful API endpoints for Agrivoltaic Dual-Axis Sun-Tracking & Dynamic Crop Shading.
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.agrivoltaic_shading import (
    AgrivoltaicDispatchDecision,
    AgrivoltaicOperationalMode,
    AgrivoltaicShadingEngine,
)
from backend.core.agrivoltaic_tracking import (
    AgrivoltaicTrackerConfig,
    AgrivoltaicTrackingEngine,
    TrackerState,
)

router = APIRouter(prefix="/agrivoltaics", tags=["Agrivoltaics & Solar Tracking"])

# Shared state
_config = AgrivoltaicTrackerConfig()
_current_mode = AgrivoltaicOperationalMode.MAX_ELECTRICITY_YIELD


class AdjustModeRequest(BaseModel):
    mode: AgrivoltaicOperationalMode


class DispatchRequest(BaseModel):
    day_of_year: int = Field(120, ge=1, le=366)
    local_hour: float = Field(12.0, ge=0.0, le=24.0)
    ambient_ghi_w_m2: float = Field(850.0, ge=0.0, le=1400.0)
    canopy_temp_c: float = Field(32.5, ge=5.0, le=50.0)
    crop_type: str = "Strawberries"


@router.get("/telemetry")
def get_agrivoltaic_telemetry() -> dict[str, Any]:
    """
    Returns real-time solar tracker geometry, generated PV power, and under-canopy microclimate.
    """
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(
        day_of_year=120,
        local_hour=11.5,
        latitude_deg=_config.latitude_deg,
        longitude_deg=_config.longitude_deg,
    )
    decision = AgrivoltaicShadingEngine.resolve_agrivoltaic_dispatch(
        solar_pos=pos,
        config=_config,
        ambient_ghi_w_m2=820.0,
        canopy_temp_c=28.5,
        crop_type="Strawberries",
        override_mode=_current_mode,
    )
    return {
        "installed_capacity_kwp": _config.installed_capacity_kwp,
        "panel_area_m2": _config.panel_area_m2,
        "clearance_height_meters": _config.clearance_height_meters,
        "active_mode": decision.active_mode.value,
        "commanded_tilt_deg": decision.commanded_tilt_deg,
        "solar_position": pos.model_dump(),
        "tracker_state": decision.tracker_state.model_dump(),
        "canopy_microclimate": decision.canopy_microclimate.model_dump(),
        "crop_stress_mitigated": decision.crop_stress_mitigated,
        "rationale": decision.rationale,
    }


@router.post("/adjust-mode")
def adjust_agrivoltaic_mode(request: AdjustModeRequest) -> dict[str, Any]:
    """
    Overrides the autonomous agrivoltaic dispatch mode.
    """
    global _current_mode
    _current_mode = request.mode
    return {
        "status": "mode_updated",
        "active_mode": _current_mode.value,
    }


@router.post("/dispatch", response_model=AgrivoltaicDispatchDecision)
def resolve_agrivoltaic_dispatch(request: DispatchRequest) -> AgrivoltaicDispatchDecision:
    """
    Dynamically computes optimal panel tilt balancing solar energy vs crop canopy protection.
    """
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(
        day_of_year=request.day_of_year,
        local_hour=request.local_hour,
        latitude_deg=_config.latitude_deg,
        longitude_deg=_config.longitude_deg,
    )
    return AgrivoltaicShadingEngine.resolve_agrivoltaic_dispatch(
        solar_pos=pos,
        config=_config,
        ambient_ghi_w_m2=request.ambient_ghi_w_m2,
        canopy_temp_c=request.canopy_temp_c,
        crop_type=request.crop_type,
        override_mode=_current_mode if _current_mode != AgrivoltaicOperationalMode.MAX_ELECTRICITY_YIELD else None,
    )


@router.get("/diurnal-profile", response_model=list[TrackerState])
def get_diurnal_tracking_profile(day_of_year: int = 120) -> list[TrackerState]:
    """
    Returns daytime astronomical tracking trajectory from 06:00 to 18:00.
    """
    return AgrivoltaicTrackingEngine.simulate_day_tracking(
        day_of_year=day_of_year,
        config=_config,
    )
