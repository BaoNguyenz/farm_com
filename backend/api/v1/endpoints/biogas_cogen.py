"""
Anaerobic Digestion & Biogas Micro-CHP Cogeneration REST API Endpoints (v1).
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.biogas_chp import (
    BiogasCHPEngine,
    CHPCogenerationResult,
    DigestateSeparationResult,
)
from backend.core.biogas_digestion import (
    AnaerobicDigesterEngine,
    DigestionSimulationResult,
    FeedstockType,
)

router = APIRouter(prefix="/biogas-cogen", tags=["Anaerobic Digestion & Biogas CHP"])

_digester_engine = AnaerobicDigesterEngine(digester_volume_m3=25.0, operating_temp_c=37.0)
_chp_engine = BiogasCHPEngine(electrical_efficiency=0.33, thermal_efficiency=0.52)


class FeedDigesterRequest(BaseModel):
    feedstock: FeedstockType = FeedstockType.CO_DIGESTION_MIX
    feed_mass_kg_day: float = Field(200.0, ge=10.0, le=2000.0)
    operating_temp_c: float | None = Field(None, ge=15.0, le=55.0)
    retention_days: float = Field(25.0, ge=5.0, le=60.0)


class CHPSimRequest(BaseModel):
    biogas_volume_m3: float = Field(15.0, ge=1.0, le=200.0)
    methane_fraction_pct: float = Field(62.0, ge=40.0, le=80.0)
    parasitic_heat_kwh: float = Field(10.0, ge=0.0, le=50.0)


class FractionateRequest(BaseModel):
    digestate_effluent_liters: float = Field(500.0, ge=50.0, le=10000.0)
    digester_temp_c: float = Field(37.0, ge=20.0, le=60.0)


@router.get("/telemetry")
async def get_biogas_telemetry() -> dict[str, Any]:
    """Retrieves operational telemetry for anaerobic digester and CHP cogeneration unit."""
    dig_res = _digester_engine.simulate_digestion(
        feedstock_type=FeedstockType.CO_DIGESTION_MIX,
        feed_mass_kg_day=180.0,
    )
    chp_res = _chp_engine.simulate_chp_generation(
        biogas_volume_m3=dig_res.daily_biogas_m3,
        methane_pct=dig_res.methane_content_pct,
    )
    sep_res = _chp_engine.fractionate_digestate(
        digestate_effluent_liters=dig_res.digestate_effluent_m3 * 1000.0,
    )
    return {
        "status": "operational",
        "digester": {
            "feedstock": dig_res.feedstock.value,
            "feed_mass_kg_day": dig_res.feed_mass_kg_day,
            "temperature_c": dig_res.digester_temp_c,
            "daily_biogas_m3": dig_res.daily_biogas_m3,
            "daily_methane_m3": dig_res.daily_methane_m3,
            "methane_content_pct": dig_res.methane_content_pct,
            "vfa_tic_ratio": dig_res.vfa_tic_ratio,
            "health_status": dig_res.health_status,
            "acidification_hazard": dig_res.acidification_hazard,
        },
        "chp_cogeneration": {
            "electricity_generated_kwh": chp_res.electricity_generated_kwh,
            "heat_recovered_kwh": chp_res.heat_recovered_kwh,
            "heat_to_greenhouse_aquaponics_kwh": chp_res.heat_to_greenhouse_aquaponics_kwh,
            "total_cogen_efficiency_pct": chp_res.total_cogen_efficiency_pct,
            "scrubbed_co2_kg": chp_res.scrubbed_co2_kg,
            "ghg_avoided_kg_co2e": chp_res.ghg_avoided_kg_co2e,
        },
        "digestate_valorization": {
            "solid_fraction_kg": sep_res.solid_fraction_kg,
            "liquid_fraction_liters": sep_res.liquid_fraction_liters,
            "liquid_n_ppm": sep_res.liquid_n_ppm,
            "pasteurization_compliant": sep_res.pasteurization_compliant,
        },
    }


@router.post("/feed-digester", response_model=DigestionSimulationResult)
async def feed_anaerobic_digester(req: FeedDigesterRequest) -> DigestionSimulationResult:
    """Feeds organic waste batch and computes kinetic biodegradation, biogas volume, and VFA/TIC."""
    return _digester_engine.simulate_digestion(
        feedstock_type=req.feedstock,
        feed_mass_kg_day=req.feed_mass_kg_day,
        override_temp_c=req.operating_temp_c,
        retention_days=req.retention_days,
    )


@router.post("/simulate-chp", response_model=CHPCogenerationResult)
async def simulate_chp_cogen(req: CHPSimRequest) -> CHPCogenerationResult:
    """Calculates electrical output, recoverable heat, and scrubbed CO2 from biogas combustion."""
    return _chp_engine.simulate_chp_generation(
        biogas_volume_m3=req.biogas_volume_m3,
        methane_pct=req.methane_fraction_pct,
        parasitic_digester_heat_demand_kwh=req.parasitic_heat_kwh,
    )


@router.post("/fractionate-digestate", response_model=DigestateSeparationResult)
async def fractionate_digestate_effluent(req: FractionateRequest) -> DigestateSeparationResult:
    """Separates raw effluent into solid organic compost and liquid bio-fertilizer extract."""
    return _chp_engine.fractionate_digestate(
        digestate_effluent_liters=req.digestate_effluent_liters,
        digester_core_temp_c=req.digester_temp_c,
    )
