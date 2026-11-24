"""
REST API Endpoints for Solar Thermal Crop Drying with Latent Heat PCM Storage.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.solar_dryer_pcm import (
    SolarDryerPCMEngine,
    SolarDryerThermalState,
)
from backend.core.solar_drying_kinetics import (
    COMMODITY_CATALOG,
    CropDryingCommodity,
    DryingBatchState,
    SolarDryingKineticsEngine,
)

router = APIRouter(prefix="/solar-dryer", tags=["Solar Thermal Crop Dryer & PCM"])

# Global singleton engines
_drying_engine = SolarDryingKineticsEngine()
_pcm_engine = SolarDryerPCMEngine()
_agronomist = AgronomistAgent()
_market = MarketAgent()


class SimulateDryingRequest(BaseModel):
    """Payload to simulate thin-layer drying of a crop batch."""
    commodity: CropDryingCommodity = CropDryingCommodity.STRAWBERRY_SLICES
    elapsed_hours: float = Field(12.0, ge=0.0, le=100.0)
    chamber_air_temp_c: float = Field(48.0, ge=20.0, le=80.0)
    chamber_air_rh_pct: float = Field(22.0, ge=5.0, le=95.0)


class PCMStatusRequest(BaseModel):
    """Payload to simulate coupled solar collector and PCM thermal state."""
    current_pcm_temp_c: float = Field(44.0, ge=10.0, le=75.0)
    ambient_temp_c: float = Field(24.0, ge=-5.0, le=45.0)
    ambient_rh_pct: float = Field(65.0, ge=10.0, le=100.0)
    solar_irradiance_w_m2: float = Field(750.0, ge=0.0, le=1300.0)
    auxiliary_heat_available_w: float = Field(0.0, ge=0.0)
    hour_of_day: float = Field(13.0, ge=0.0, le=24.0)


class DryingQualityAuditRequest(BaseModel):
    """Payload to audit produce quality, water activity, and nutrient retention."""
    commodity: str = "strawberry_slices"
    water_activity_aw: float = Field(0.55, ge=0.0, le=1.0)
    moisture_wb_pct: float = Field(11.5, ge=0.0, le=100.0)
    vitamin_c_retention_pct: float = Field(74.0, ge=0.0, le=100.0)
    chamber_temp_c: float = Field(48.0, ge=15.0, le=80.0)


@router.get("/telemetry")
def get_solar_dryer_telemetry() -> dict[str, Any]:
    """Retrieves live thermal state of collector, PCM storage bed, active drying batch, and economics."""
    # Simulate current thermal equilibrium
    thermal = _pcm_engine.step_dryer_thermal(
        current_pcm_temp_c=46.5,
        ambient_temp_c=24.5,
        ambient_rh_pct=60.0,
        solar_irradiance_w_m2=720.0,
        hour_of_day=13.5,
    )

    batch = _drying_engine.simulate_drying_step(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        elapsed_hours=14.0,
        chamber_air_temp_c=thermal.chamber_inlet_temp_c,
        chamber_air_rh_pct=thermal.chamber_air_rh_pct,
    )

    quality_audit = _agronomist.audit_drying_batch_quality(
        commodity="strawberry_slices",
        water_activity_aw=batch.water_activity_aw,
        moisture_wb_pct=batch.moisture_wet_basis_pct,
        vitamin_c_retention_pct=batch.vitamin_c_retention_pct,
        chamber_temp_c=thermal.chamber_inlet_temp_c,
    )

    economics = _market.evaluate_solar_drying_economic_margin(
        fresh_mass_kg=50.0,
        fresh_price_vnd_kg=75000.0,
        dried_price_vnd_kg=680000.0,
        yield_ratio=0.13,
    )

    return {
        "facility_status": "ONLINE_ACTIVE_DRYING",
        "thermal_system": thermal.model_dump(),
        "active_batch": batch.model_dump(),
        "quality_audit": quality_audit,
        "economics": economics,
        "available_commodities": [c.value for c in COMMODITY_CATALOG],
    }


@router.post("/simulate-drying", response_model=DryingBatchState)
def simulate_crop_drying(req: SimulateDryingRequest) -> DryingBatchState:
    """Calculates thin-layer moisture decay, effective diffusivity, and Vitamin C retention."""
    return _drying_engine.simulate_drying_step(
        commodity=req.commodity,
        elapsed_hours=req.elapsed_hours,
        chamber_air_temp_c=req.chamber_air_temp_c,
        chamber_air_rh_pct=req.chamber_air_rh_pct,
    )


@router.post("/pcm-status", response_model=SolarDryerThermalState)
def evaluate_pcm_thermal_state(req: PCMStatusRequest) -> SolarDryerThermalState:
    """Computes solar collector heat gain, PCM charging/discharging enthalpy, and chamber air temp."""
    return _pcm_engine.step_dryer_thermal(
        current_pcm_temp_c=req.current_pcm_temp_c,
        ambient_temp_c=req.ambient_temp_c,
        ambient_rh_pct=req.ambient_rh_pct,
        solar_irradiance_w_m2=req.solar_irradiance_w_m2,
        auxiliary_heat_available_w=req.auxiliary_heat_available_w,
        hour_of_day=req.hour_of_day,
    )


@router.post("/audit-quality")
def audit_drying_quality(req: DryingQualityAuditRequest) -> dict[str, Any]:
    """Audits water activity a_w threshold, thermal thresholds, and export grade compliance."""
    return _agronomist.audit_drying_batch_quality(
        commodity=req.commodity,
        water_activity_aw=req.water_activity_aw,
        moisture_wb_pct=req.moisture_wb_pct,
        vitamin_c_retention_pct=req.vitamin_c_retention_pct,
        chamber_temp_c=req.chamber_temp_c,
    )
