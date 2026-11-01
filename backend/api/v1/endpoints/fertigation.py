"""
Precision Fertigation & Hydrology REST API Endpoints (v1).

Provides nutritional dosing recipes (Tank A, Tank B, Acid buffer),
leaching fraction recommendations, and water reservoir solvency monitoring.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin
from backend.core.fertigation import FertigationOptimizer, FertigationRecipe
from backend.core.water_budget import WaterBudgetManager, WaterBudgetReport, ReservoirState
from backend.core.heat_stress import CanopyHeatStressController, HeatStressAssessment


router = APIRouter(prefix="/fertigation", tags=["Precision Fertigation & Hydrology"])

# Singleton farm water budget manager instance
_global_water_budget = WaterBudgetManager(ReservoirState())


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


class RechargeRequest(BaseModel):
    """Payload to simulate weather or groundwater refill into reservoir."""
    elapsed_hours: float = Field(1.0, ge=0.1, le=72.0)
    precipitation_mm: float = Field(0.0, ge=0.0)


@router.get("/recipes")
async def list_fertigation_recipes(
    raw_water_ec: float = Query(0.25, ge=0.0, le=2.0, description="Raw source water EC in mS/cm"),
    raw_water_ph: float = Query(7.4, ge=4.0, le=9.5, description="Raw source water pH"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> List[FertigationRecipe]:
    """Computes stage-specific fertigation recipes across all zones in the farm."""
    return FertigationOptimizer.batch_optimize_farm(
        farm=farm,
        raw_water_ec_ms_cm=raw_water_ec,
        raw_water_ph=raw_water_ph
    )


@router.get("/recipes/{zone_id}")
async def get_zone_recipe(
    zone_id: str,
    raw_water_ec: float = Query(0.25, ge=0.0, le=2.0),
    raw_water_ph: float = Query(7.4, ge=4.0, le=9.5),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> FertigationRecipe:
    """Retrieves precision fertilizer recipe for a specific plot zone."""
    zone = farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    return FertigationOptimizer.compute_recipe(
        zone=zone,
        raw_water_ec_ms_cm=raw_water_ec,
        raw_water_ph=raw_water_ph
    )


@router.get("/water-budget")
async def get_water_budget(
    avg_burn_liters: float = Query(2500.0, ge=100.0, description="Estimated daily farm water consumption")
) -> WaterBudgetReport:
    """Retrieves current water storage, rationing tier, and days of autonomy."""
    return _global_water_budget.get_budget_report(avg_daily_burn_liters=avg_burn_liters)


@router.post("/water-budget/recharge")
async def recharge_reservoir(req: RechargeRequest) -> Dict[str, Any]:
    """Advances reservoir state with groundwater inflow and precipitation catchment."""
    _global_water_budget.step(
        elapsed_hours=req.elapsed_hours,
        precipitation_mm=req.precipitation_mm
    )
    rep = _global_water_budget.get_budget_report()
    return {
        "status": "recharged",
        "elapsed_hours": req.elapsed_hours,
        "precipitation_mm": req.precipitation_mm,
        "report": rep.model_dump()
    }


@router.get("/cooling/status")
async def get_canopy_cooling_status(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Assesses microclimate heat stress and evaporative fogging requirements."""
    w = farm.current_weather
    assessment: HeatStressAssessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=w.temp_c,
        humidity_percent=w.humidity_percent,
        solar_radiation_mj=w.solar_radiation_mj
    )

    action = CanopyHeatStressController.dispatch_misting_action(
        assessment=assessment,
        zone_ids=[z.id for z in farm.zones],
        water_available=_global_water_budget.evaluate_rationing_tier() != "critical_empty"
    )

    return {
        "assessment": assessment.model_dump(),
        "dispatcher_action": action
    }
