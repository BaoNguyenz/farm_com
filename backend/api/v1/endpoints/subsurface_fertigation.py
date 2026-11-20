"""
Subsurface Drip Irrigation & Precision Fertigation REST API Endpoints (v1).
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.fertigation_solute import (
    FertigationMixResult,
    FertigationRecipe,
    FertigationSoluteEngine,
    SoluteTransportPoint,
)
from backend.core.irrigation_hydraulics import (
    SoilTextureClass,
    UnsaturatedHydraulicsEngine,
    WettedBulbGeometry,
)

router = APIRouter(prefix="/subsurface-fertigation", tags=["Subsurface Drip & Fertigation"])

_hydraulics_engine = UnsaturatedHydraulicsEngine(SoilTextureClass.LOAM)
_fertigation_engine = FertigationSoluteEngine()


class BulbSimRequest(BaseModel):
    soil_type: SoilTextureClass = SoilTextureClass.LOAM
    emitter_depth_cm: float = Field(20.0, ge=5.0, le=50.0)
    emitter_discharge_lph: float = Field(1.6, ge=0.5, le=10.0)
    application_duration_hours: float = Field(2.0, ge=0.1, le=12.0)
    initial_moisture: float = Field(0.18, ge=0.05, le=0.45)


class FertigationMixRequest(BaseModel):
    recipe: FertigationRecipe = FertigationRecipe.FRUITING
    irrigation_flow_rate_lph: float = Field(1500.0, ge=100.0, le=20000.0)
    measured_ec: float | None = Field(None, ge=0.0, le=5.0)
    measured_ph: float | None = Field(None, ge=3.0, le=10.0)


class SoluteProfileRequest(BaseModel):
    surface_ec: float = Field(2.4, ge=0.5, le=5.0)
    soil_depth_cm: float = Field(60.0, ge=20.0, le=120.0)
    pore_water_velocity_cm_h: float = Field(2.5, ge=0.5, le=10.0)
    elapsed_hours: float = Field(4.0, ge=0.5, le=24.0)


@router.get("/telemetry")
async def get_subsurface_telemetry() -> dict[str, Any]:
    """Retrieves live telemetry for subsurface drip network and dosing station."""
    bulb = _hydraulics_engine.simulate_subsurface_wetted_bulb(
        emitter_depth_cm=20.0,
        emitter_discharge_lph=1.6,
        application_duration_hours=2.0,
        initial_volumetric_moisture=0.22,
    )
    mix = _fertigation_engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.FRUITING,
        irrigation_flow_rate_lph=2000.0,
    )
    return {
        "status": "operational",
        "soil_type": _hydraulics_engine.soil_type.value,
        "default_recipe": mix.recipe.value,
        "wetted_bulb": {
            "depth_cm": bulb.depth_cm,
            "radial_width_cm": bulb.radial_width_cm,
            "vertical_height_cm": bulb.vertical_height_cm,
            "matric_suction_kpa": bulb.matric_suction_kpa,
            "effective_saturation": bulb.effective_saturation,
            "deep_percolation_loss_pct": bulb.deep_percolation_loss_pct,
        },
        "fertigation_station": {
            "measured_ec_ms_cm": mix.measured_ec_ms_cm,
            "target_ec_ms_cm": mix.target_ec_ms_cm,
            "measured_ph": mix.measured_ph,
            "target_ph": mix.target_ph,
            "stock_a_flow_lph": mix.stock_a_injection_lph,
            "stock_b_flow_lph": mix.stock_b_injection_lph,
            "acid_c_flow_lph": mix.acid_c_injection_lph,
            "leaching_fraction_pct": mix.leaching_fraction_pct,
            "salinity_hazard_warning": mix.salinity_hazard_warning,
        },
    }


@router.post("/simulate-bulb", response_model=WettedBulbGeometry)
async def simulate_wetted_bulb(req: BulbSimRequest) -> WettedBulbGeometry:
    """Simulates unsaturated hydraulic expansion of the wetted bulb around buried emitters."""
    engine = UnsaturatedHydraulicsEngine(req.soil_type)
    return engine.simulate_subsurface_wetted_bulb(
        emitter_depth_cm=req.emitter_depth_cm,
        emitter_discharge_lph=req.emitter_discharge_lph,
        application_duration_hours=req.application_duration_hours,
        initial_volumetric_moisture=req.initial_moisture,
    )


@router.post("/mix-dosing", response_model=FertigationMixResult)
async def calculate_fertigation_dosing(req: FertigationMixRequest) -> FertigationMixResult:
    """Calculates precision multi-channel Venturi injection rates and leaching fraction."""
    return _fertigation_engine.compute_pid_injection_rates(
        target_recipe=req.recipe,
        irrigation_flow_rate_lph=req.irrigation_flow_rate_lph,
        measured_ec=req.measured_ec,
        measured_ph=req.measured_ph,
    )


@router.post("/solute-profile", response_model=list[SoluteTransportPoint])
async def compute_solute_transport_profile(req: SoluteProfileRequest) -> list[SoluteTransportPoint]:
    """Computes vertical 1D solute advection-dispersion concentration through the root zone."""
    return _fertigation_engine.simulate_1d_solute_transport(
        surface_ec=req.surface_ec,
        soil_depth_cm=req.soil_depth_cm,
        pore_water_velocity_cm_h=req.pore_water_velocity_cm_h,
        elapsed_hours=req.elapsed_hours,
    )
