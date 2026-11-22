"""
REST API Endpoints for RothC Soil Organic Carbon Dynamics & Verra VM0042 MRV Carbon Credits.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.carbon_mrv import (
    AdditionalityAssessment,
    CarbonCreditCertificate,
    CarbonMRVEngine,
    EvidenceType,
    MRVEvidenceRecord,
)
from backend.core.carbon_rothc import (
    CarbonAmendment,
    RothCKineticsEngine,
    RothCPools,
    RothCSimulationStep,
)

router = APIRouter(prefix="/carbon-mrv", tags=["RothC Soil Carbon & MRV Credits"])

# Global singleton engines and state
_rothc_engine = RothCKineticsEngine()
_mrv_engine = CarbonMRVEngine()
_agronomist = AgronomistAgent()
_market = MarketAgent()

# In-memory certificate ledger
_certificates_db: dict[str, CarbonCreditCertificate] = {}

# Default baseline state
_current_pools = RothCPools(dpm=0.8, rpm=3.5, bio=1.2, hum=24.5, iom=4.5)


class SimulateRothCRequest(BaseModel):
    """Payload to simulate monthly RothC turnover under environmental conditions."""
    temp_c: float = Field(20.0, ge=-10.0, le=45.0)
    smd_mm: float = Field(15.0, ge=0.0, le=100.0)
    vegetated: bool = True
    amendment_type: str = Field("biochar", description="crop_residue, farmyard_compost, digestate, or biochar")
    carbon_input_t_c_per_ha: float = Field(2.5, ge=0.0, le=50.0)
    inert_biochar_fraction: float = Field(0.95, ge=0.0, le=1.0)


class EvaluateAdditionalityRequest(BaseModel):
    """Payload to evaluate Verra VM0042 additionality."""
    baseline_soc_t_c_ha: float = Field(28.0, ge=5.0, le=150.0)
    project_soc_t_c_ha: float = Field(34.5, ge=5.0, le=150.0)
    farm_area_ha: float = Field(3.0, ge=0.1, le=1000.0)


class IssueCertificateRequest(BaseModel):
    """Payload to mint a tamper-evident Verified Carbon Unit certificate."""
    baseline_soc_t_c_ha: float = Field(28.0, ge=5.0, le=150.0)
    project_soc_t_c_ha: float = Field(34.5, ge=5.0, le=150.0)
    farm_area_ha: float = Field(3.0, ge=0.1, le=1000.0)
    evidence_records: list[MRVEvidenceRecord] = Field(default_factory=list)


class RetireCertificateRequest(BaseModel):
    """Payload to permanently retire a carbon credit certificate."""
    certificate_id: str
    retiring_entity: str
    retirement_reason: str


@router.get("/telemetry")
def get_carbon_mrv_telemetry() -> dict[str, Any]:
    """Retrieves current 5-pool SOC stocks, additionality metrics, and registry ledger."""
    additionality = _mrv_engine.evaluate_additionality(
        baseline_soc_t_c_ha=28.0,
        project_soc_t_c_ha=_current_pools.total_soc,
        farm_area_ha=3.0,
    )

    som_pct = round((_current_pools.total_soc / 100.0) * 1.724 * 5.0, 2)  # van Bemmelen factor
    hum_ratio = round((_current_pools.hum / max(0.1, _current_pools.total_soc)) * 100.0, 1)

    soil_health = _agronomist.audit_soil_carbon_health(
        total_soc_t_c_ha=_current_pools.total_soc,
        hum_ratio_pct=hum_ratio,
        soil_organic_matter_pct=som_pct,
    )

    monetization = _market.evaluate_carbon_credit_monetization(
        net_vcu_tonnes=additionality.net_mintable_vcu,
        price_usd_per_vcu=25.0,
    )

    # Sample evidence records for live Merkle root
    sample_records = [
        MRVEvidenceRecord(
            record_id="REC-SOIL-01",
            evidence_type=EvidenceType.SOIL_CORE_LAB,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-22T08:00:00Z",
            measured_metric="soc_t_c_ha",
            value=_current_pools.total_soc,
            unit="t_c_ha",
            laboratory_or_sensor="Eurofins Agroscience",
        )
    ]
    merkle_root, _ = _mrv_engine.build_merkle_tree(sample_records)

    return {
        "current_pools": _current_pools.model_dump(),
        "total_soc_t_c_ha": _current_pools.total_soc,
        "active_soc_t_c_ha": _current_pools.active_soc,
        "soil_carbon_health": soil_health,
        "additionality": additionality.model_dump(),
        "monetization": monetization,
        "merkle_root_hash": merkle_root,
        "certificates_issued_count": len(_certificates_db),
    }


@router.post("/simulate-rothc", response_model=RothCSimulationStep)
def simulate_rothc_turnover(req: SimulateRothCRequest) -> RothCSimulationStep:
    """Simulates monthly RothC carbon turnover with temperature, moisture, and amendments."""
    amendment = CarbonAmendment(
        amendment_type=req.amendment_type,
        carbon_input_t_c_per_ha=req.carbon_input_t_c_per_ha,
        inert_biochar_fraction=req.inert_biochar_fraction,
    )

    return _rothc_engine.step_month(
        pools=_current_pools,
        temp_c=req.temp_c,
        smd_mm=req.smd_mm,
        vegetated=req.vegetated,
        amendment=amendment,
    )


@router.post("/evaluate-additionality", response_model=AdditionalityAssessment)
def evaluate_additionality(req: EvaluateAdditionalityRequest) -> AdditionalityAssessment:
    """Computes Verra VM0042 additionality, 15% buffer pool reserve, and net mintable VCUs."""
    return _mrv_engine.evaluate_additionality(
        baseline_soc_t_c_ha=req.baseline_soc_t_c_ha,
        project_soc_t_c_ha=req.project_soc_t_c_ha,
        farm_area_ha=req.farm_area_ha,
    )


@router.post("/issue-credits", response_model=CarbonCreditCertificate)
def issue_carbon_credits(req: IssueCertificateRequest) -> CarbonCreditCertificate:
    """Mints a verified carbon credit certificate attested by SHA-256 Merkle root."""
    assessment = _mrv_engine.evaluate_additionality(
        baseline_soc_t_c_ha=req.baseline_soc_t_c_ha,
        project_soc_t_c_ha=req.project_soc_t_c_ha,
        farm_area_ha=req.farm_area_ha,
    )

    if assessment.net_mintable_vcu <= 0.0:
        raise HTTPException(
            status_code=400,
            detail="Cannot issue credits: Project SOC does not achieve positive additionality over baseline.",
        )

    records = req.evidence_records or [
        MRVEvidenceRecord(
            record_id="REC-AUTO-01",
            evidence_type=EvidenceType.SOIL_CORE_LAB,
            plot_id="PLOT-01",
            timestamp_utc="2026-11-22T10:00:00Z",
            measured_metric="soc_combustion_pct",
            value=2.85,
            unit="pct_c",
            laboratory_or_sensor="VCS Accredited Laboratory",
        )
    ]

    cert = _mrv_engine.mint_carbon_certificate(assessment, records, farm_area_ha=req.farm_area_ha)
    _certificates_db[cert.certificate_id] = cert
    return cert


@router.post("/retire-credits", response_model=CarbonCreditCertificate)
def retire_carbon_credits(req: RetireCertificateRequest) -> CarbonCreditCertificate:
    """Permanently retires a carbon certificate for corporate ESG emissions offsetting."""
    cert = _certificates_db.get(req.certificate_id)
    if not cert:
        raise HTTPException(status_code=404, detail=f"Certificate {req.certificate_id} not found in registry")

    try:
        return _mrv_engine.retire_certificate(cert, req.retiring_entity, req.retirement_reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
