"""
Water Resilience, Smart Rainwater Harvesting & Solar Desalination REST Endpoints.
Provides telemetry, runoff catchment harvesting, and solar RO batch execution.
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.rainwater_harvesting import (
    HarvestEventReport,
    RainwaterHarvestingEngine,
)
from backend.core.solar_desalination import (
    DesalinationBatchResult,
    SolarDesalinationEngine,
)

router = APIRouter(prefix="/water-resilience", tags=["water-resilience"])
rainwater_engine = RainwaterHarvestingEngine()
desalination_engine = SolarDesalinationEngine()


class RainRunoffHarvestRequest(BaseModel):
    rainfall_mm: float = Field(..., ge=0.0, le=300.0, description="Precipitation depth in mm")
    duration_hours: float = Field(1.0, ge=0.1, le=48.0, description="Storm duration in hours")
    raw_turbidity_ntu: float = Field(35.0, ge=1.0, le=200.0, description="Raw roof runoff turbidity NTU")


class DesalinationRunRequest(BaseModel):
    feed_tds_ppm: float = Field(2200.0, ge=100.0, le=10000.0, description="Groundwater salinity in mg/L TDS")
    feed_volume_m3: float = Field(4.0, ge=0.5, le=50.0, description="Volume to treat in m3")
    solar_available_kw: float = Field(2.5, ge=0.0, le=10.0, description="Solar PV power allocated to RO pump in kW")
    target_pressure_bar: float = Field(14.0, ge=5.0, le=25.0, description="Operating booster pressure")
    use_erd: bool = Field(True, description="Enable Energy Recovery Device")


class RainwaterWithdrawalRequest(BaseModel):
    volume_liters: float = Field(..., ge=1.0, description="Volume of clean rainwater to withdraw in liters")


@router.get("/telemetry")
def get_water_resilience_telemetry() -> dict[str, Any]:
    """
    Returns consolidated water resilience telemetry:
    Rainwater cistern levels, first-flush filtration, and solar RO capabilities.
    """
    cistern = rainwater_engine.get_cistern_status()
    salinity_hazard = desalination_engine.assess_crop_salinity_hazard(
        raw_tds_ppm=1450.0,
        crop_type="Strawberries",
    )

    if cistern.fill_percentage >= 50.0:
        resilience_status = "optimal_rainwater_reserves"
    elif salinity_hazard["salinity_exceeded"]:
        resilience_status = "salinity_stress_ro_required"
    else:
        resilience_status = "moderate_resilience"

    return {
        "resilience_status": resilience_status,
        "rainwater_cistern": {
            "capacity_liters": cistern.capacity_liters,
            "current_storage_liters": cistern.current_liters,
            "fill_percentage": cistern.fill_percentage,
            "is_spilling_overflow": cistern.is_spilling_overflow,
            "catchment_area_m2": rainwater_engine.catchment.area_m2,
            "runoff_coefficient": rainwater_engine.catchment.runoff_coefficient,
            "water_ec_ds_m": 0.05,
        },
        "solar_desalination": {
            "membrane_type": "Thin Film Composite (TFC 4040 BWRO)",
            "membrane_area_m2": desalination_engine.MEMBRANE_AREA_M2,
            "nominal_salt_rejection_pct": desalination_engine.MEMBRANE_SALT_REJECTION,
            "pump_max_power_kw": desalination_engine.PUMP_MAX_POWER_KW,
            "crop_salinity_thresholds": desalination_engine.CROP_TDS_THRESHOLDS,
            "groundwater_assessment": salinity_hazard,
        },
    }


@router.post("/harvest-runoff", response_model=HarvestEventReport)
def harvest_rainwater_runoff(payload: RainRunoffHarvestRequest) -> HarvestEventReport:
    """
    Simulates a storm event across the greenhouse catchment, performs first-flush diversion,
    sediment disc filtration, and storage update.
    """
    return rainwater_engine.process_precipitation_event(
        rainfall_mm=payload.rainfall_mm,
        duration_hours=payload.duration_hours,
        raw_turbidity_ntu=payload.raw_turbidity_ntu,
    )


@router.post("/run-desalination", response_model=DesalinationBatchResult)
def run_solar_desalination(payload: DesalinationRunRequest) -> DesalinationBatchResult:
    """
    Commands an autonomous batch run of the solar RO desalination system.
    Adjusts operating pressure and permeate flux based on available solar PV kW.
    """
    return desalination_engine.run_desalination_cycle(
        feed_tds_ppm=payload.feed_tds_ppm,
        feed_volume_m3=payload.feed_volume_m3,
        solar_available_kw=payload.solar_available_kw,
        target_pressure_bar=payload.target_pressure_bar,
        use_erd=payload.use_erd,
    )


@router.post("/withdraw-rainwater")
def withdraw_rainwater(payload: RainwaterWithdrawalRequest) -> dict[str, Any]:
    """
    Discharges clean rainwater for fertigation blending or root-zone flushing.
    """
    withdrawn = rainwater_engine.withdraw_water(payload.volume_liters)
    cistern = rainwater_engine.get_cistern_status()
    return {
        "requested_liters": payload.volume_liters,
        "withdrawn_liters": withdrawn,
        "remaining_storage_liters": cistern.current_liters,
        "fill_percentage": cistern.fill_percentage,
    }
