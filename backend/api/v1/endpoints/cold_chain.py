"""
Post-Harvest Cold-Chain Telemetry, Arrhenius Shelf-Life, and Ethylene Scrubber REST Endpoints.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.cold_chain import (
    ColdChainEngine,
    ColdChamberState,
    ShelfLifeProjection,
)

router = APIRouter(prefix="/cold-chain", tags=["cold-chain"])
cold_engine = ColdChainEngine()


class TemperatureAdjustmentRequest(BaseModel):
    chamber_id: str = Field(..., description="Cold storage chamber identifier (e.g. CHAMBER-A1)")
    target_temp_c: float = Field(..., ge=-2.0, le=25.0, description="Target set-point preservation temperature in °C")


class EthylenePurgeRequest(BaseModel):
    chamber_id: str = Field(..., description="Cold storage chamber identifier")


@router.get("/chambers", response_model=list[ColdChamberState])
def get_all_chambers() -> list[ColdChamberState]:
    """
    Returns real-time telemetry from all cold storage chambers (temperature, humidity, ethylene ppm).
    """
    return list(cold_engine.chambers.values())


@router.get("/audit", response_model=list[ShelfLifeProjection])
def audit_cold_chain_shelf_life() -> list[ShelfLifeProjection]:
    """
    Calculates dynamic Q10 produce respiration, remaining shelf-life days, and freshness grading.
    """
    return cold_engine.audit_all_chambers()


@router.get("/chamber/{chamber_id}")
def get_chamber_details(chamber_id: str) -> dict[str, Any]:
    """
    Retrieves detailed microclimate telemetry and shelf-life projection for a specific cold room.
    """
    chamber = cold_engine.chambers.get(chamber_id)
    if not chamber:
        raise HTTPException(status_code=404, detail=f"Chamber '{chamber_id}' not found in cold storage network")
    proj = cold_engine.evaluate_shelf_life(chamber)
    return {
        "chamber": chamber.model_dump(),
        "shelf_life_projection": proj.model_dump(),
    }


@router.post("/adjust-temperature")
def adjust_chamber_temperature(payload: TemperatureAdjustmentRequest) -> dict[str, Any]:
    """
    Adjusts refrigeration setpoint temperature for a cold room.
    """
    chamber = cold_engine.chambers.get(payload.chamber_id)
    if not chamber:
        raise HTTPException(status_code=404, detail=f"Chamber '{payload.chamber_id}' not found")

    chamber.target_temp_c = payload.target_temp_c
    chamber.air_temp_c = payload.target_temp_c  # Fast chilling convergence
    proj = cold_engine.evaluate_shelf_life(chamber)

    return {
        "status": "success",
        "chamber_id": payload.chamber_id,
        "new_target_temp_c": payload.target_temp_c,
        "updated_shelf_life_days": proj.remaining_shelf_life_days,
        "quality_grade": proj.quality_grade,
    }


@router.post("/purge-ethylene")
def purge_chamber_ethylene(payload: EthylenePurgeRequest) -> dict[str, Any]:
    """
    Activates catalytic ethylene scrubber, dropping C2H4 to baseline trace levels (0.02 ppm).
    """
    chamber = cold_engine.chambers.get(payload.chamber_id)
    if not chamber:
        raise HTTPException(status_code=404, detail=f"Chamber '{payload.chamber_id}' not found")

    chamber.scrubber_active = True
    chamber.ethylene_ppm = 0.02
    proj = cold_engine.evaluate_shelf_life(chamber)

    return {
        "status": "success",
        "chamber_id": payload.chamber_id,
        "ethylene_ppm": chamber.ethylene_ppm,
        "scrubber_active": chamber.scrubber_active,
        "senescence_slowdown_factor": proj.ethylene_senescence_factor,
        "action_summary": f"Ethylene scrubbed to 0.02 ppm in {payload.chamber_id}. Shelf-life preserved.",
    }
