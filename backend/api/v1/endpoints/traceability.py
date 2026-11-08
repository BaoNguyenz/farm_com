"""
RESTful Endpoints for VietGAP Food Safety Compliance, PHI Monitoring & Batch Traceability.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.core.traceability import (
    ChemicalApplicationRecord,
    HarvestBatchPassport,
    TraceabilityEngine,
    VietGAPAuditReport,
    WaterSafetyProfile,
)
from backend.core.twin_state import create_default_farm

router = APIRouter(prefix="/traceability", tags=["VietGAP Traceability & Food Safety"])

_default_farm = create_default_farm()
_trace_engine = TraceabilityEngine(
    water_safety=WaterSafetyProfile(
        e_coli_cfu_per_100ml=15.0,
        total_coliform_cfu_per_100ml=220.0,
        lead_pb_ppm=0.005,
        cadmium_cd_ppm=0.001,
        arsenic_as_ppm=0.003,
    )
)


class TreatmentLogRequest(BaseModel):
    """Payload to log a biological or chemical application to a zone."""
    zone_id: str = Field(..., description="Target plot zone ID (e.g. 'Z_0_0')")
    substance_name: str = Field(..., description="Active substance or formulation name")
    substance_type: str = Field("bio_fungicide", description="bio_fungicide, organic_nutrient, chemical")
    dosage_per_ha: float = Field(2.5, ge=0.1, le=50.0, description="Dosage in liters or kg per hectare")
    phi_days: float | None = Field(None, ge=0.0, le=90.0, description="Pre-Harvest Interval in days (optional override)")


class MintPassportRequest(BaseModel):
    """Payload to mint a cryptographic batch passport for harvested produce."""
    zone_id: str = Field(..., description="Harvested plot zone ID")
    weight_kg: float = Field(..., gt=0.0, le=10000.0, description="Harvested fresh weight in kg")


@router.get("/compliance-audit", response_model=VietGAPAuditReport)
def get_vietgap_compliance_audit() -> VietGAPAuditReport:
    """
    Perform complete farm-wide VietGAP & GlobalGAP food safety audit.
    """
    return _trace_engine.audit_compliance(_default_farm)


@router.post("/treatment/log", response_model=ChemicalApplicationRecord)
def log_crop_treatment(req: TreatmentLogRequest) -> ChemicalApplicationRecord:
    """
    Record an agrochemical or bio-intervention and initiate Pre-Harvest Interval (PHI) tracking.
    """
    target = _default_farm.get_zone(req.zone_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Zone '{req.zone_id}' not found in farm digital twin.")

    return _trace_engine.log_treatment(
        zone_id=req.zone_id,
        substance_name=req.substance_name,
        substance_type=req.substance_type,
        dosage_per_ha=req.dosage_per_ha,
        phi_days=req.phi_days,
    )


@router.post("/batch/passport", response_model=HarvestBatchPassport)
def mint_harvest_batch_passport(req: MintPassportRequest) -> HarvestBatchPassport:
    """
    Generate verifiable digital batch passport with SHA-256 cryptographic provenance signature.
    """
    target = _default_farm.get_zone(req.zone_id)
    if not target:
        raise HTTPException(status_code=404, detail=f"Zone '{req.zone_id}' not found in farm digital twin.")

    return _trace_engine.generate_batch_passport(
        farm_id=_default_farm.farm_id,
        zone=target,
        weight_kg=req.weight_kg,
    )


@router.get("/water-quality")
def get_water_safety_profile() -> dict[str, Any]:
    """
    Retrieve irrigation water safety test results and TCVN 6774 conformity.
    """
    w = _trace_engine.water_safety
    return {
        "is_compliant": w.is_compliant,
        "standard": "TCVN 6774:2000 & VietGAP TCVN 11892-1:2017",
        "parameters": {
            "e_coli_cfu_per_100ml": {"value": w.e_coli_cfu_per_100ml, "limit": 100.0, "status": "safe"},
            "total_coliform_cfu_per_100ml": {"value": w.total_coliform_cfu_per_100ml, "limit": 1000.0, "status": "safe"},
            "lead_pb_ppm": {"value": w.lead_pb_ppm, "limit": 0.05, "status": "safe"},
            "cadmium_cd_ppm": {"value": w.cadmium_cd_ppm, "limit": 0.01, "status": "safe"},
            "arsenic_as_ppm": {"value": w.arsenic_as_ppm, "limit": 0.05, "status": "safe"},
        },
    }
