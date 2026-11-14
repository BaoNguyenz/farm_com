"""
Soil Microbiome Ecology, Nutrient Leaching, and Root Hypoxia REST Endpoints.
"""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.soil_microbiome import (
    FarmSoilHealthReport,
    MicrobialPopulationProfile,
    SoilMicrobiomeEngine,
    ZoneSoilEcologyAudit,
)
from backend.core.twin_state import create_default_farm

router = APIRouter(prefix="/soil-microbiome", tags=["soil-microbiome"])
soil_engine = SoilMicrobiomeEngine()
current_farm = create_default_farm()


class ReinoculationRequest(BaseModel):
    zone_id: str = Field(..., description="Target plot zone identifier (e.g. Z_1_1)")
    organic_amendment_kg: float = Field(50.0, ge=0.0, le=500.0)
    bio_inoculant: bool = Field(True, description="Whether to apply mycorrhizae/Trichoderma inoculant")


@router.get("/health", response_model=FarmSoilHealthReport)
def get_farm_soil_health(percolation_hours: float = 1.0) -> FarmSoilHealthReport:
    """
    Returns farm-wide composite Soil Health Index (SHI), nitrogen leaching audit, and hypoxia flags.
    """
    return soil_engine.audit_farm(current_farm, percolation_hours=percolation_hours)


@router.get("/zone/{zone_id}", response_model=ZoneSoilEcologyAudit)
def get_zone_soil_audit(zone_id: str, percolation_hours: float = 1.0) -> ZoneSoilEcologyAudit:
    """
    Returns granular microbiological vigor, percolation drainage, and leaching metrics for a zone.
    """
    zone = current_farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found in farm twin")
    return soil_engine.audit_zone(zone, percolation_hours=percolation_hours)


@router.get("/leaching-risk")
def get_leaching_risk_overview() -> dict[str, Any]:
    """
    Identifies high-vulnerability zones for fertilizer runoff and waterlogging hypoxia.
    """
    report = soil_engine.audit_farm(current_farm)
    at_risk_zones = [
        za for za in report.zone_audits
        if za.leaching_risk_tier in ("moderate", "critical_leaching") or za.root_hypoxia_index > 0.2
    ]
    return {
        "farm_id": current_farm.farm_id,
        "total_at_risk_zones": len(at_risk_zones),
        "total_estimated_leached_n_kg": report.total_estimated_leached_n_kg,
        "average_soil_health_index": report.average_soil_health_index,
        "at_risk_details": [za.model_dump() for za in at_risk_zones],
        "mitigation_protocol": (
            "Throttle drip fertigation lines; increase drainage ditch flow; apply biological "
            "Trichoderma harzianum inoculants to restore beneficial fungal mycorrhizae."
        ),
    }


@router.post("/reinoculate")
def reinoculate_zone(payload: ReinoculationRequest) -> dict[str, Any]:
    """
    Simulates biological re-inoculation and biochar/organic compost amendment on a degraded plot.
    """
    zone = current_farm.get_zone(payload.zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{payload.zone_id}' not found in farm twin")

    audit = soil_engine.audit_zone(zone)
    recovered_profile: MicrobialPopulationProfile = soil_engine.simulate_microbiome_recovery(
        audit=audit,
        organic_amendment_kg=payload.organic_amendment_kg,
        bio_inoculant=payload.bio_inoculant,
    )

    return {
        "status": "success",
        "zone_id": payload.zone_id,
        "message": f"Successfully applied biological treatment to zone {payload.zone_id}",
        "treatment_details": audit.recommended_bio_treatment,
        "post_treatment_profile": recovered_profile.model_dump(),
    }
