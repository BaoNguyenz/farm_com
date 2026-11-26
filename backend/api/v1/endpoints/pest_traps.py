"""
REST API Endpoints for Smart Optical-Pheromone Pest Traps & Atmospheric Plume Dispersion.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.pheromone_dispersion import (
    PheromoneDispersionEngine,
    PlumeSimulationResult,
    TargetPestSpecies,
)
from backend.core.smart_pest_trap import (
    OpticalTrapCatch,
    SmartPestTrapEngine,
    TrapPopulationAudit,
)

router = APIRouter(prefix="/pest-traps", tags=["Smart Optical-Pheromone Pest Traps"])

_plume_engine = PheromoneDispersionEngine()
_trap_engine = SmartPestTrapEngine()
_agronomist = AgronomistAgent()
_market = MarketAgent()


class SimulatePlumeRequest(BaseModel):
    """Payload to simulate downwind pheromone plume dispersion."""
    species: TargetPestSpecies = TargetPestSpecies.SPODOPTERA_LITURA
    ambient_temp_c: float = Field(22.0, ge=5.0, le=45.0)
    wind_speed_m_s: float = Field(1.8, ge=0.2, le=20.0)
    solar_irradiance_w_m2: float = Field(0.0, ge=0.0, le=1200.0)


class RecordCatchRequest(BaseModel):
    """Payload to evaluate optical sticky-trap catches and PDD phenology."""
    species: TargetPestSpecies = TargetPestSpecies.SPODOPTERA_LITURA
    catches: list[OpticalTrapCatch]
    cumulative_pdd: float = Field(360.0, ge=0.0)


@router.get("/telemetry")
def get_pest_traps_telemetry() -> dict[str, Any]:
    """Retrieves live optical trap network counts, pheromone plume range, and IPM economics."""
    plume = _plume_engine.simulate_plume(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        ambient_temp_c=21.5,
        wind_speed_m_s=1.6,
        solar_irradiance_w_m2=0.0,
    )
    sample_catches = [
        OpticalTrapCatch(trap_id="TRAP-NORTH-01", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=3),
        OpticalTrapCatch(trap_id="TRAP-SOUTH-02", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=4),
    ]
    population = _trap_engine.evaluate_trap_network(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        catches=sample_catches,
        cumulative_pdd=358.0,
    )
    ipm_audit = _agronomist.audit_pest_trap_threshold(
        species=population.species.value,
        mean_moths_per_trap_night=population.mean_moths_per_trap_night,
        economic_threshold=population.economic_threshold,
        disruption_radius_m=plume.mating_disruption_radius_m,
    )
    economics = _market.evaluate_pheromone_mating_disruption_roi(
        farm_area_ha=3.0,
        dispensers_per_ha=plume.recommended_dispensers_per_ha,
    )

    return {
        "network_status": "ACTIVE_OPTICAL_MONITORING",
        "plume_dispersion": plume.model_dump(),
        "population_audit": population.model_dump(),
        "ipm_audit": ipm_audit,
        "economics": economics,
    }


@router.post("/simulate-plume", response_model=PlumeSimulationResult)
def simulate_pheromone_plume(req: SimulatePlumeRequest) -> PlumeSimulationResult:
    """Simulates Gaussian atmospheric pheromone plume dispersion."""
    return _plume_engine.simulate_plume(
        species=req.species,
        ambient_temp_c=req.ambient_temp_c,
        wind_speed_m_s=req.wind_speed_m_s,
        solar_irradiance_w_m2=req.solar_irradiance_w_m2,
    )


@router.post("/record-catch", response_model=TrapPopulationAudit)
def evaluate_trap_catches(req: RecordCatchRequest) -> TrapPopulationAudit:
    """Aggregates optical trap counts and evaluates Economic Threshold alerts."""
    return _trap_engine.evaluate_trap_network(
        species=req.species,
        catches=req.catches,
        cumulative_pdd=req.cumulative_pdd,
    )
