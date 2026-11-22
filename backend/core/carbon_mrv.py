"""
Verra VM0042 & Gold Standard MRV Carbon Accounting & Merkle Attestation Engine.

Implements Measurement, Reporting, and Verification (MRV) for voluntary carbon markets:
- Verra VCS VM0042 Additionality: Baseline vs Project SOC differentiation.
- Non-permanence Buffer Pool deductions (15%) and conservative uncertainty margins.
- Net Verified Carbon Unit (VCU) issuance: 1 VCU = 1 metric tonne CO2 equivalent sequestered.
- SHA-256 Merkle Tree cryptographic batch attestation over physical soil core lab tests,
  multispectral UAV surveys, and IoT telemetry receipts.
- Complete certificate lifecycle: Minting, Third-party Verification, and Permanent Retirement.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class CreditStatus(str, Enum):
    """Lifecycle status of a Verified Carbon Unit (VCU)."""
    MINTED = "minted"
    VERIFIED = "verified"
    RETIRED = "retired"


class EvidenceType(str, Enum):
    """Source verification evidence for MRV audit."""
    SOIL_CORE_LAB = "soil_core_lab"
    UAV_MULTISPECTRAL = "uav_multispectral"
    IOT_MATRIC_TENSION = "iot_matric_tension"
    AMENDMENT_RECEIPT = "amendment_receipt"


class MRVEvidenceRecord(BaseModel):
    """Tamper-evident record of empirical field measurement."""
    record_id: str
    evidence_type: EvidenceType
    plot_id: str
    timestamp_utc: str
    measured_metric: str
    value: float
    unit: str
    laboratory_or_sensor: str
    metadata_hash: str = ""

    def compute_leaf_hash(self) -> str:
        """Computes SHA-256 cryptographic digest of the evidence record."""
        payload = f"{self.record_id}|{self.evidence_type.value}|{self.plot_id}|{self.timestamp_utc}|{self.measured_metric}|{self.value}|{self.unit}|{self.laboratory_or_sensor}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MerkleAuditProof(BaseModel):
    """Cryptographic audit proof demonstrating inclusion of a record in the batch Merkle root."""
    record_id: str
    leaf_hash: str
    audit_trail_hashes: list[str]
    merkle_root: str
    is_valid: bool


class CarbonCreditCertificate(BaseModel):
    """Verra VCS VM0042 compliant Verified Carbon Unit (VCU) asset."""
    certificate_id: str = Field(default_factory=lambda: f"VCU-{uuid.uuid4().hex[:8].upper()}")
    project_id: str = "VCS-AGRI-DALAT-042"
    vintage_year: int = 2026
    methodology: str = "VERRA_VM0042_V2"
    area_ha: float
    gross_sequestration_t_co2e: float
    buffer_pool_deduction_t_co2e: float
    uncertainty_deduction_t_co2e: float
    net_credits_issued_t_co2e: float
    merkle_root_hash: str
    status: CreditStatus = CreditStatus.MINTED
    issuance_timestamp: str = ""
    retired_by: str | None = None
    retirement_reason: str | None = None


class AdditionalityAssessment(BaseModel):
    """Quantitative baseline vs project additionality calculation."""
    baseline_soc_t_c_ha: float
    project_soc_t_c_ha: float
    net_additionality_t_c_ha: float
    gross_co2e_t_ha: float
    total_gross_co2e_tonnes: float
    buffer_pool_tonnes: float
    uncertainty_discount_tonnes: float
    net_mintable_vcu: float
    market_value_usd: float
    market_value_vnd: float


@dataclass
class CarbonMRVEngine:
    """
    Executes Verra VM0042 carbon additionality calculations and Merkle tree attestations.
    """
    C_TO_CO2E_RATIO: ClassVar[float] = 44.0 / 12.0  # 3.667 t CO2e per t C
    BUFFER_POOL_PCT: ClassVar[float] = 15.0  # 15% non-permanence buffer pool reserve
    UNCERTAINTY_DISCOUNT_PCT: ClassVar[float] = 5.0  # 5% conservative discount
    CARBON_PRICE_USD_PER_TONNE: ClassVar[float] = 25.0  # $25/t CO2e voluntary premium
    VND_PER_USD: ClassVar[float] = 25400.0

    @classmethod
    def build_merkle_tree(cls, records: list[MRVEvidenceRecord]) -> tuple[str, list[str]]:
        """
        Builds a binary SHA-256 Merkle tree from empirical MRV records.
        Returns (merkle_root_hash, leaf_hashes).
        """
        if not records:
            empty_hash = hashlib.sha256(b"EMPTY_TREE").hexdigest()
            return empty_hash, []

        leaf_hashes = [r.compute_leaf_hash() for r in records]
        current_layer = list(leaf_hashes)

        while len(current_layer) > 1:
            next_layer: list[str] = []
            for i in range(0, len(current_layer), 2):
                h1 = current_layer[i]
                h2 = current_layer[i + 1] if i + 1 < len(current_layer) else h1
                combined = hashlib.sha256((h1 + h2).encode("utf-8")).hexdigest()
                next_layer.append(combined)
            current_layer = next_layer

        return current_layer[0], leaf_hashes

    def evaluate_additionality(
        self,
        baseline_soc_t_c_ha: float,
        project_soc_t_c_ha: float,
        farm_area_ha: float = 3.0,
    ) -> AdditionalityAssessment:
        """
        Calculates net additionality according to Verra VM0042 rules:
        Gross additionality = (Project SOC - Baseline SOC) * (44 / 12) * Area
        Net VCUs = Gross - 15% buffer pool - 5% uncertainty discount
        """
        if project_soc_t_c_ha < baseline_soc_t_c_ha:
            # No additionality (soil carbon depleted relative to baseline)
            delta_c = 0.0
        else:
            delta_c = project_soc_t_c_ha - baseline_soc_t_c_ha

        gross_co2e_per_ha = delta_c * self.C_TO_CO2E_RATIO
        total_gross = gross_co2e_per_ha * farm_area_ha

        buffer_pool = total_gross * (self.BUFFER_POOL_PCT / 100.0)
        uncertainty = total_gross * (self.UNCERTAINTY_DISCOUNT_PCT / 100.0)

        net_vcu = max(0.0, total_gross - buffer_pool - uncertainty)
        val_usd = net_vcu * self.CARBON_PRICE_USD_PER_TONNE
        val_vnd = val_usd * self.VND_PER_USD

        return AdditionalityAssessment(
            baseline_soc_t_c_ha=round(baseline_soc_t_c_ha, 3),
            project_soc_t_c_ha=round(project_soc_t_c_ha, 3),
            net_additionality_t_c_ha=round(delta_c, 3),
            gross_co2e_t_ha=round(gross_co2e_per_ha, 3),
            total_gross_co2e_tonnes=round(total_gross, 3),
            buffer_pool_tonnes=round(buffer_pool, 3),
            uncertainty_discount_tonnes=round(uncertainty, 3),
            net_mintable_vcu=round(net_vcu, 3),
            market_value_usd=round(val_usd, 2),
            market_value_vnd=round(val_vnd, 0),
        )

    def mint_carbon_certificate(
        self,
        assessment: AdditionalityAssessment,
        evidence_records: list[MRVEvidenceRecord],
        farm_area_ha: float = 3.0,
    ) -> CarbonCreditCertificate:
        """
        Mints a tamper-evident carbon certificate backed by Merkle root attestation.
        """
        merkle_root, _ = self.build_merkle_tree(evidence_records)

        return CarbonCreditCertificate(
            area_ha=farm_area_ha,
            gross_sequestration_t_co2e=assessment.total_gross_co2e_tonnes,
            buffer_pool_deduction_t_co2e=assessment.buffer_pool_tonnes,
            uncertainty_deduction_t_co2e=assessment.uncertainty_discount_tonnes,
            net_credits_issued_t_co2e=assessment.net_mintable_vcu,
            merkle_root_hash=merkle_root,
            status=CreditStatus.MINTED,
            issuance_timestamp="2026-11-22T12:00:00Z",
        )

    @staticmethod
    def retire_certificate(
        cert: CarbonCreditCertificate,
        retiring_entity: str,
        reason: str,
    ) -> CarbonCreditCertificate:
        """
        Permanently retires a carbon certificate to offset corporate Scope 1/2 emissions.
        """
        if cert.status == CreditStatus.RETIRED:
            raise ValueError(f"Certificate {cert.certificate_id} is already retired")

        cert.status = CreditStatus.RETIRED
        cert.retired_by = retiring_entity
        cert.retirement_reason = reason
        return cert
