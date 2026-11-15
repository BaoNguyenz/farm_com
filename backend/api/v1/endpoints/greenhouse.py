"""
Controlled Environment Agriculture (CEA) Greenhouse REST Endpoints.
Provides microclimate telemetry, motorized vent controls, and photosynthetic CO2 dosing.
"""
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.greenhouse_cea import GreenhouseCEAEngine, GreenhouseMicroclimate

router = APIRouter(prefix="/greenhouse", tags=["greenhouse"])
greenhouse_engine = GreenhouseCEAEngine(greenhouse_id="GH-POLYHOUSE-01")


class VentAdjustmentRequest(BaseModel):
    roof_vent_pct: float = Field(..., ge=0.0, le=100.0, description="Target ridge vent aperture percentage")
    side_curtain_pct: float = Field(..., ge=0.0, le=100.0, description="Roll-up side curtain opening percentage")
    pad_and_fan_active: bool = Field(False, description="Evaporative cellulose wet pad and exhaust fans")
    shade_screen_deployed: bool = Field(False, description="Thermal reflective shade screen")


class CO2InjectionRequest(BaseModel):
    target_co2_ppm: float = Field(850.0, ge=350.0, le=2000.0, description="Target greenhouse CO2 concentration")
    dosing_rate_kg_h: float = Field(4.5, ge=0.1, le=25.0, description="Injection flow rate in kg/hour")
    force_override: bool = Field(False, description="Bypass anti-exhaust vent interlock check")


@router.get("/telemetry", response_model=GreenhouseMicroclimate)
def get_greenhouse_telemetry(
    ambient_temp_c: float = Query(24.0, description="External ambient temperature in °C"),
    ambient_humidity_pct: float = Query(65.0, description="External relative humidity %"),
    solar_radiation_mj: float = Query(18.0, description="Daily solar radiation in MJ/m2-day"),
) -> GreenhouseMicroclimate:
    """
    Returns real-time CEA greenhouse microclimate, VPD, CO2 ppm, and net photosynthesis.
    """
    return greenhouse_engine.regulate_microclimate(
        ambient_temp_c=ambient_temp_c,
        ambient_humidity_pct=ambient_humidity_pct,
        solar_radiation_mj=solar_radiation_mj,
    )


@router.post("/adjust-vents", response_model=GreenhouseMicroclimate)
def adjust_greenhouse_vents(payload: VentAdjustmentRequest) -> GreenhouseMicroclimate:
    """
    Commands motorized ridge vents, side roll-ups, and evaporative wet pads.
    Enforces anti-exhaust CO2 shutoff if roof vents are opened >= 55%.
    """
    greenhouse_engine.actuators.roof_vent_pct = payload.roof_vent_pct
    greenhouse_engine.actuators.side_curtain_pct = payload.side_curtain_pct
    greenhouse_engine.actuators.pad_and_fan_active = payload.pad_and_fan_active
    greenhouse_engine.actuators.shade_screen_deployed = payload.shade_screen_deployed

    # Interlock: close CO2 valve if vents are opened
    if payload.roof_vent_pct >= 55.0 and greenhouse_engine.actuators.co2_dosing_valve_open:
        greenhouse_engine.actuators.co2_dosing_valve_open = False
        greenhouse_engine.actuators.co2_dosing_rate_kg_h = 0.0

    return greenhouse_engine.regulate_microclimate(
        ambient_temp_c=25.0,
        ambient_humidity_pct=60.0,
        solar_radiation_mj=16.0,
    )


@router.post("/inject-co2", response_model=GreenhouseMicroclimate)
def inject_photosynthetic_co2(payload: CO2InjectionRequest) -> GreenhouseMicroclimate:
    """
    Activates liquid CO2 gas injection to elevate photosynthetic carbon assimilation.
    Guards against atmospheric exhaust loss when roof vents exceed 55% aperture.
    """
    if greenhouse_engine.actuators.roof_vent_pct >= 55.0 and not payload.force_override:
        raise HTTPException(
            status_code=400,
            detail=(
                f"ANTI-EXHAUST INTERLOCK: Roof vents are opened to {greenhouse_engine.actuators.roof_vent_pct:.1f}%. "
                f"CO2 injection rejected to prevent atmospheric gas dissipation."
            ),
        )

    greenhouse_engine.actuators.co2_dosing_valve_open = True
    greenhouse_engine.actuators.co2_dosing_rate_kg_h = payload.dosing_rate_kg_h
    greenhouse_engine.current_co2_ppm = payload.target_co2_ppm

    return greenhouse_engine.regulate_microclimate(
        ambient_temp_c=24.0,
        ambient_humidity_pct=62.0,
        solar_radiation_mj=18.0,
        target_co2_ppm=payload.target_co2_ppm,
    )


@router.get("/photosynthesis-curve", response_model=list[dict[str, Any]])
def get_photosynthesis_curve(
    co2_ppm: float = Query(800.0, ge=300.0, le=2000.0),
    temp_c: float = Query(24.0, ge=10.0, le=45.0),
) -> list[dict[str, Any]]:
    """
    Generates the PAR vs net photosynthetic assimilation curve (Michaelis-Menten kinetics).
    """
    par_levels = [0, 50, 100, 200, 400, 600, 800, 1000, 1200, 1500]
    return [
        {
            "par_umol_m2_s": par,
            "pn_umol_m2_s": greenhouse_engine.calculate_photosynthesis(float(par), co2_ppm, temp_c),
        }
        for par in par_levels
    ]
