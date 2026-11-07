"""
RESTful Endpoints for Predictive Crop Yield Forecasting & Post-Harvest Logistics Management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.twin_state import create_default_farm
from backend.core.yield_prediction import (
    FarmYieldHarvestReport,
    HarvestLogisticsPlan,
    YieldPredictionEngine,
    ZoneYieldForecast,
)

router = APIRouter(prefix="/yield", tags=["Predictive Yield & Harvest Logistics"])

_engine = YieldPredictionEngine()
_default_farm = create_default_farm()


class ZoneSimulationRequest(BaseModel):
    """Payload to trigger Monte Carlo stochastic simulation on a specific zone."""
    zone_id: str = Field(..., description="Target plot zone identifier (e.g. 'Z_0_0')")
    simulation_runs: int = Field(250, ge=50, le=2000, description="Number of stochastic simulation iterations")
    ambient_temp_c: float = Field(22.0, ge=-5.0, le=45.0, description="Assumed average daily temperature in °C")


@router.get("/forecast", response_model=FarmYieldHarvestReport)
def get_farm_yield_forecast() -> FarmYieldHarvestReport:
    """
    Retrieve comprehensive biophysical harvest yield forecast and logistics plan for the entire farm.
    """
    return _engine.forecast_farm(farm=_default_farm)


@router.post("/zone-simulation", response_model=ZoneYieldForecast)
def simulate_zone_yield(req: ZoneSimulationRequest) -> ZoneYieldForecast:
    """
    Execute high-resolution Monte Carlo yield simulation with confidence intervals for a single zone.
    """
    target_zone = next((z for z in _default_farm.zones if z.id == req.zone_id), None)
    if not target_zone:
        raise HTTPException(status_code=404, detail=f"Zone '{req.zone_id}' not found in farm digital twin.")

    return _engine.forecast_zone(
        zone=target_zone,
        avg_daily_temp_c=req.ambient_temp_c,
        simulation_runs=req.simulation_runs,
    )


@router.get("/harvest-schedule", response_model=HarvestLogisticsPlan)
def get_harvest_logistics_schedule() -> HarvestLogisticsPlan:
    """
    Retrieve cold-chain crate requirements, labor picking shifts, and pre-cooling energy budget.
    """
    report = _engine.forecast_farm(farm=_default_farm)
    return report.logistics_plan
