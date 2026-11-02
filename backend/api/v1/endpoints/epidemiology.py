"""
Fungal Epidemiology & Biosecurity REST API Endpoints (v1).

Exposes microclimatic pathogen risk indices (Botrytis, Phytophthora, Powdery Mildew)
and Integrated Pest Management (IPM) biological control prescriptions.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from backend.core.twin_state import FarmDigitalTwin
from backend.core.epidemiology import (
    EpidemiologyEngine,
    ZoneEpidemiologyProfile,
)


router = APIRouter(prefix="/epidemiology", tags=["Fungal Epidemiology & Biosecurity"])


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


@router.get("/biosecurity")
async def get_farm_biosecurity_audit(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Retrieves consolidated farm-wide epidemiological risk audit."""
    return EpidemiologyEngine.evaluate_farm_biosecurity(farm)


@router.get("/zones/{zone_id}")
async def get_zone_epidemiology_profile(
    zone_id: str,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> ZoneEpidemiologyProfile:
    """Retrieves pathogen risk assessments and treatment recommendations for a single zone."""
    zone = farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    return EpidemiologyEngine.evaluate_zone_pathogens(zone, farm.current_weather)


@router.get("/ipm-advisories")
async def get_ipm_advisories(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> List[Dict[str, Any]]:
    """Gathers actionable Integrated Pest Management (IPM) bio-control advisories across zones."""
    profiles = [EpidemiologyEngine.evaluate_zone_pathogens(z, farm.current_weather) for z in farm.zones]

    advisories: List[Dict[str, Any]] = []
    for p in profiles:
        if p.biosecurity_alert_level in ("moderate", "high", "critical"):
            advisories.append({
                "zone_id": p.zone_id,
                "crop_type": p.crop_type,
                "alert_level": p.biosecurity_alert_level,
                "primary_threat": p.primary_threat,
                "recommended_action": p.recommended_action
            })

    return advisories
