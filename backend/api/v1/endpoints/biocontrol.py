"""
RESTful API endpoints for Biological Pest Control, Holling Type II Predation, and Macro-Biologic Dispersal.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.biocontrol import (
    BiocontrolKineticsEngine,
    PopulationState,
    PredatorSpecies,
    PreySpecies,
)
from backend.core.biocontrol_dispersion import (
    FarmReleaseManifest,
    MacroBiologicDispersionEngine,
    ZoneReleasePlan,
)
from backend.core.biocontrol_safety import (
    BiocontrolSafetyEngine,
    SafetyClearanceReport,
    SprayApplication,
)

router = APIRouter(prefix="/biocontrol", tags=["Biological Pest Control"])


class PredationSimulationRequest(BaseModel):
    initial_prey: float = Field(25.0, ge=0.0)
    initial_predator: float = Field(4.0, ge=0.0)
    days: int = Field(10, ge=1, le=60)
    temp_c: float = Field(25.0, ge=10.0, le=40.0)
    predator_species: PredatorSpecies = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS
    prey_species: PreySpecies = PreySpecies.TWO_SPOTTED_SPIDER_MITE


class SafetyCheckRequest(BaseModel):
    target_beneficial: str = "phytoseiulus_persimilis"
    spray_history: list[SprayApplication] = Field(default_factory=list)


class ZoneReleaseRequest(BaseModel):
    zone_id: str = "ZONE_STRAWBERRY_B"
    canopy_area_m2: float = Field(600.0, gt=0.0)
    pest_density: float = Field(12.0, ge=0.0)
    target_pest: PreySpecies = PreySpecies.TWO_SPOTTED_SPIDER_MITE
    beneficial_species: PredatorSpecies = PredatorSpecies.PHYTOSEIULUS_PERSIMILIS
    use_drone: bool = True


@router.get("/telemetry")
def get_biocontrol_telemetry() -> dict[str, Any]:
    """
    Returns current biocontrol readiness, active biological species, and standard packaging profiles.
    """
    return {
        "status": "active",
        "beneficial_agents_active": [
            {
                "species": PredatorSpecies.PHYTOSEIULUS_PERSIMILIS.value,
                "common_name": "Phytoseiid predatory mite",
                "target": "Two-spotted spider mite (Tetranychus urticae)",
                "status": "established",
            },
            {
                "species": "encarsia_formosa",
                "common_name": "Parasitoid wasp",
                "target": "Greenhouse whitefly (Trialeurodes vaporariorum)",
                "status": "monitoring",
            },
        ],
        "economic_threshold_spider_mite": 5.0,
        "economic_injury_level_spider_mite": 15.0,
        "available_predator_species": [s.value for s in PredatorSpecies],
        "monitored_prey_species": [s.value for s in PreySpecies],
    }


@router.post("/simulate-predation", response_model=list[PopulationState])
def simulate_predation_kinetics(request: PredationSimulationRequest) -> list[PopulationState]:
    """
    Simulates multi-day predator-prey population trajectory using Holling Type II functional response.
    """
    try:
        return BiocontrolKineticsEngine.simulate_timeline(
            initial_prey=request.initial_prey,
            initial_predator=request.initial_predator,
            days=request.days,
            temp_c=request.temp_c,
            predator_species=request.predator_species,
            prey_species=request.prey_species,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {e}") from e


@router.post("/check-safety", response_model=SafetyClearanceReport)
def check_release_safety(request: SafetyCheckRequest) -> SafetyClearanceReport:
    """
    Evaluates pesticide residue degradation on canopy foliage to certify release safety for beneficials.
    """
    return BiocontrolSafetyEngine.evaluate_release_safety(
        spray_history=request.spray_history,
        target_beneficial=request.target_beneficial,
    )


@router.post("/plan-zone-release", response_model=ZoneReleasePlan)
def plan_zone_release(request: ZoneReleaseRequest) -> ZoneReleasePlan:
    """
    Calculates precision dose rate, canister requirements, and drone aerial hopper calibration.
    """
    return MacroBiologicDispersionEngine.plan_zone_release(
        zone_id=request.zone_id,
        canopy_area_m2=request.canopy_area_m2,
        pest_density=request.pest_density,
        target_pest=request.target_pest,
        beneficial_species=request.beneficial_species,
        use_drone=request.use_drone,
    )


@router.post("/plan-farm-manifest", response_model=FarmReleaseManifest)
def plan_farm_manifest(zone_specs: list[dict[str, Any]]) -> FarmReleaseManifest:
    """
    Aggregates multi-zone scouting densities into a consolidated commercial release manifest.
    """
    if not zone_specs:
        raise HTTPException(status_code=400, detail="zone_specs list cannot be empty")
    return MacroBiologicDispersionEngine.generate_farm_manifest(zone_specs)
