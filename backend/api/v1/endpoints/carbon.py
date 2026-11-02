"""
Farm GHG Emissions & Carbon Accounting REST API Endpoints (v1).

Provides Scope 1 and Scope 2 carbon footprint calculations,
soil sequestration offsets, and climate resilience ratings.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends

from backend.core.twin_state import FarmDigitalTwin
from backend.core.carbon_accounting import (
    CarbonAccountingEngine,
    FarmCarbonReport,
    ZoneCarbonFootprint,
    CarbonEmissionFactors,
)


router = APIRouter(prefix="/carbon", tags=["GHG Emissions & Carbon Accounting"])

_global_carbon_engine = CarbonAccountingEngine()


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


@router.get("/footprint")
async def get_farm_carbon_footprint(
    elapsed_days: float = Query(1.0, ge=0.1, le=365.0, description="Time horizon in days"),
    water_liters: float = Query(2500.0, ge=0.0, description="Total irrigation water drawn"),
    nitrogen_kg: float = Query(1.5, ge=0.0, description="Total synthetic N fertilizer applied"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> FarmCarbonReport:
    """Calculates consolidated farm-wide GHG footprint and climate rating."""
    return _global_carbon_engine.calculate_farm_emissions(
        farm=farm,
        elapsed_days=elapsed_days,
        total_water_liters=water_liters,
        total_nitrogen_kg=nitrogen_kg
    )


@router.get("/zones/{zone_id}")
async def get_zone_carbon_footprint(
    zone_id: str,
    water_liters: float = Query(150.0, ge=0.0),
    nitrogen_kg: float = Query(0.1, ge=0.0),
    elapsed_days: float = Query(1.0, ge=0.1, le=365.0),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> ZoneCarbonFootprint:
    """Calculates specific carbon footprint for an individual plot zone."""
    zone = farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    return _global_carbon_engine.calculate_zone_emissions(
        zone=zone,
        water_liters_used=water_liters,
        nitrogen_applied_kg=nitrogen_kg,
        elapsed_days=elapsed_days
    )


@router.get("/factors")
async def get_emission_factors() -> Dict[str, Any]:
    """Retrieves standard emission factors applied for EVN electricity and fertilization."""
    factors: CarbonEmissionFactors = _global_carbon_engine.factors
    return factors.model_dump()
