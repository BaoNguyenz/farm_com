"""
RESTful API endpoints for Recirculating Aquaponics Systems (RAS), Nitrification & DWC Hydroponics.
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.aquaponics_hydroponics import BaseChemical, BufferDosingRecommendation
from backend.core.aquaponics_system import (
    AquaponicEcosystemCoordinator,
    AquaponicEcosystemTelemetry,
)

router = APIRouter(prefix="/aquaponics", tags=["Recirculating Aquaponics"])

_coordinator = AquaponicEcosystemCoordinator()


class FeedBatchRequest(BaseModel):
    feed_kg: float = Field(0.8, gt=0.0, le=15.0)
    crude_protein_pct: float = Field(32.0, ge=20.0, le=55.0)


class BufferAlkalinityRequest(BaseModel):
    chemical: BaseChemical = BaseChemical.POTASSIUM_BICARBONATE
    target_alkalinity_mg_l: float = Field(100.0, ge=60.0, le=180.0)


class SimulateCycleRequest(BaseModel):
    hours: float = Field(1.0, ge=0.1, le=48.0)
    feed_input_kg: float = Field(0.0, ge=0.0)
    par_umol_m2_s: float = Field(400.0, ge=50.0, le=1200.0)
    supplementary_aeration: bool = True


@router.get("/telemetry", response_model=AquaponicEcosystemTelemetry)
def get_aquaponics_telemetry() -> AquaponicEcosystemTelemetry:
    """
    Returns real-time biophysical telemetry from fish rearing tank, MBBR biofilter, and DWC hydroponic beds.
    """
    return _coordinator.step_simulation_cycle(feed_input_kg=0.0, dt_hours=0.1)


@router.post("/feed-batch")
def feed_fish_batch(request: FeedBatchRequest) -> dict[str, Any]:
    """
    Simulates feed consumption by fish biomass, calculates TAN excretion spike and oxygen consumption.
    """
    telemetry = _coordinator.step_simulation_cycle(
        feed_input_kg=request.feed_kg,
        dt_hours=1.0,
    )
    return {
        "status": "feed_administered",
        "feed_kg": request.feed_kg,
        "protein_pct": request.crude_protein_pct,
        "fish_biomass_kg": telemetry.total_fish_biomass_kg,
        "current_tan_mg_l": telemetry.fish_tank.tan_mg_l,
        "toxic_nh3_mg_l": telemetry.fish_tank.toxic_nh3_mg_l,
        "dissolved_oxygen_mg_l": telemetry.fish_tank.dissolved_oxygen_mg_l,
        "ecosystem_status": telemetry.ecosystem_status.value,
    }


@router.post("/buffer-alkalinity", response_model=BufferDosingRecommendation)
def buffer_system_alkalinity(request: BufferAlkalinityRequest) -> BufferDosingRecommendation:
    """
    Doses alkaline buffer (KHCO3 or Ca(OH)2) to neutralize biofilter nitrification acidity and protect fish and plants.
    """
    return _coordinator.dose_alkalinity_buffer(
        chemical=request.chemical,
        target_alkalinity_mg_l=request.target_alkalinity_mg_l,
    )


@router.post("/simulate-cycle", response_model=AquaponicEcosystemTelemetry)
def simulate_aquaponic_cycle(request: SimulateCycleRequest) -> AquaponicEcosystemTelemetry:
    """
    Simulates recirculating water turnover across aquaculture tanks, moving bed biofilter, and plant beds.
    """
    return _coordinator.step_simulation_cycle(
        feed_input_kg=request.feed_input_kg,
        par_umol_m2_s=request.par_umol_m2_s,
        supplementary_aeration=request.supplementary_aeration,
        dt_hours=request.hours,
    )
