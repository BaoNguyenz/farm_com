"""
VietGAP & GlobalGAP Food Safety, Pre-Harvest Interval (PHI) & Batch Traceability Engine.

Enforces:
- TCVN 11892-1:2017 (VietGAP Horticulture Standards)
- GlobalG.A.P. Integrated Farm Assurance (IFA v6)
- Pre-Harvest Interval (PHI) residue monitoring and chemical clearance
- Microbiological & heavy metal irrigation water safety testing (TCVN 6774:2000)
- Cryptographic SHA-256 Batch Passport generation for export provenance
"""

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin, PlotZone


class ChemicalApplicationRecord(BaseModel):
    """Log of agrochemical, bio-fungicide, or foliar nutrition applied to a zone."""
    treatment_id: str
    zone_id: str
    substance_name: str
    substance_type: str  # bio_fungicide, organic_nutrient, copper_chelate, synthetic
    application_timestamp: float
    phi_days_required: float = Field(..., description="Mandatory Pre-Harvest Interval in days")
    dosage_per_ha: float
    operator_id: str = "AUTO-DRONE-01"

    def days_elapsed(self, current_time: float | None = None) -> float:
        """Calculate days since application."""
        now = current_time if current_time is not None else time.time()
        return max(0.0, (now - self.application_timestamp) / 86400.0)

    def is_cleared_for_harvest(self, current_time: float | None = None) -> bool:
        """True if days elapsed meets or exceeds mandatory PHI."""
        return self.days_elapsed(current_time) >= self.phi_days_required


class WaterSafetyProfile(BaseModel):
    """Microbiological and heavy metal water quality assay for irrigation source."""
    e_coli_cfu_per_100ml: float = Field(12.0, description="E. coli CFU/100ml (VietGAP max 100)")
    total_coliform_cfu_per_100ml: float = Field(180.0, description="Total coliform CFU/100ml (VietGAP max 1000)")
    lead_pb_ppm: float = Field(0.008, description="Lead Pb concentration (Limit 0.05 ppm)")
    cadmium_cd_ppm: float = Field(0.001, description="Cadmium Cd concentration (Limit 0.01 ppm)")
    arsenic_as_ppm: float = Field(0.005, description="Arsenic As concentration (Limit 0.05 ppm)")

    @property
    def is_compliant(self) -> bool:
        """Check all parameters against VietGAP / TCVN 6774 standards."""
        return (
            self.e_coli_cfu_per_100ml <= 100.0
            and self.total_coliform_cfu_per_100ml <= 1000.0
            and self.lead_pb_ppm <= 0.05
            and self.cadmium_cd_ppm <= 0.01
            and self.arsenic_as_ppm <= 0.05
        )


class HarvestBatchPassport(BaseModel):
    """Tamper-evident verifiable digital provenance certificate for produce export."""
    batch_id: str
    farm_id: str
    zone_id: str
    crop_type: str
    harvest_date_utc: str
    weight_kg: float
    phi_clearance: bool
    remaining_phi_hours: float
    certifications_eligible: list[str]
    compliance_score: float
    digital_signature_hash: str
    qr_payload: str


class VietGAPAuditReport(BaseModel):
    """Enterprise compliance audit scorecard."""
    farm_id: str
    audit_timestamp_utc: str
    overall_compliance_score: float = Field(..., ge=0.0, le=100.0)
    compliance_tier: str  # AAA_EXPORT_READY, AA_DOMESTIC_PREMIUM, A_STANDARD, NON_COMPLIANT
    water_safety_passed: bool
    active_treatments_count: int
    zones_ready_for_harvest_count: int
    zones_in_phi_quarantine_count: int
    quarantine_advisories: list[str]


class TraceabilityEngine:
    """
    Evaluates Pre-Harvest Intervals (PHI), validates water quality, and mints
    cryptographic produce passports.
    """

    STANDARD_PHI_DAYS: ClassVar[dict[str, float]] = {
        "Bacillus subtilis": 1.0,
        "Trichoderma asperellum": 1.0,
        "Copper Hydroxide": 7.0,
        "Azoxystrobin": 14.0,
        "Organic Neem Oil": 2.0,
        "Potassium Silicate": 1.0,
    }

    def __init__(self, water_safety: WaterSafetyProfile | None = None) -> None:
        self.water_safety = water_safety or WaterSafetyProfile()
        self._application_logs: list[ChemicalApplicationRecord] = []

    def log_treatment(
        self,
        zone_id: str,
        substance_name: str,
        substance_type: str = "bio_fungicide",
        dosage_per_ha: float = 2.5,
        phi_days: float | None = None,
        timestamp: float | None = None,
    ) -> ChemicalApplicationRecord:
        """Record an agrochemical or biological intervention."""
        phi = phi_days if phi_days is not None else self.STANDARD_PHI_DAYS.get(substance_name, 7.0)
        t_time = timestamp if timestamp is not None else time.time()
        record = ChemicalApplicationRecord(
            treatment_id=f"TRT-{int(t_time)}-{zone_id}",
            zone_id=zone_id,
            substance_name=substance_name,
            substance_type=substance_type,
            application_timestamp=t_time,
            phi_days_required=phi,
            dosage_per_ha=dosage_per_ha,
        )
        self._application_logs.append(record)
        return record

    def check_zone_phi(self, zone_id: str, current_time: float | None = None) -> tuple[bool, float, list[str]]:
        """
        Check if zone is cleared of all active chemical Pre-Harvest Intervals.
        Returns (is_cleared, max_remaining_hours, active_substances).
        """
        now = current_time if current_time is not None else time.time()
        active_substances: list[str] = []
        max_remaining_hours = 0.0

        for rec in self._application_logs:
            if rec.zone_id == zone_id:
                days_left = rec.phi_days_required - rec.days_elapsed(now)
                if days_left > 0.0:
                    hours_left = round(days_left * 24.0, 1)
                    max_remaining_hours = max(max_remaining_hours, hours_left)
                    active_substances.append(f"{rec.substance_name} (PHI: {hours_left}h left)")

        is_cleared = (max_remaining_hours == 0.0)
        return (is_cleared, max_remaining_hours, active_substances)

    def generate_batch_passport(
        self,
        farm_id: str,
        zone: PlotZone,
        weight_kg: float,
        current_time: float | None = None,
    ) -> HarvestBatchPassport:
        """
        Mint a verifiable cryptographic batch passport for harvested produce.
        """
        now = current_time if current_time is not None else time.time()
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        batch_id = f"VGAP-{date_str.replace('-', '')}-{zone.id}-{zone.crop_type[:3].upper()}"

        cleared, remaining_hours, _ = self.check_zone_phi(zone.id, now)

        # Compliance score calculation
        water_ok = self.water_safety.is_compliant
        score = 100.0
        if not cleared:
            score -= 40.0
        if not water_ok:
            score -= 30.0
        if zone.health_status == "diseased":
            score -= 20.0

        certs: list[str] = []
        if score >= 90.0:
            certs = ["VietGAP (TCVN 11892)", "GlobalG.A.P. IFA v6 Ready"]
        elif score >= 75.0:
            certs = ["VietGAP (TCVN 11892)"]
        else:
            certs = ["Quarantine - Not Certified"]

        # Genesis signature
        payload_data = {
            "batch_id": batch_id,
            "farm": farm_id,
            "zone": zone.id,
            "crop": zone.crop_type,
            "weight_kg": weight_kg,
            "phi_clearance": cleared,
            "timestamp": now,
        }
        sig_hash = hashlib.sha256(json.dumps(payload_data, sort_keys=True).encode()).hexdigest()
        qr_payload = f"https://trace.farm.vn/verify/{batch_id}?sig={sig_hash[:16]}"

        return HarvestBatchPassport(
            batch_id=batch_id,
            farm_id=farm_id,
            zone_id=zone.id,
            crop_type=zone.crop_type,
            harvest_date_utc=datetime.now(UTC).isoformat(),
            weight_kg=round(weight_kg, 2),
            phi_clearance=cleared,
            remaining_phi_hours=remaining_hours,
            certifications_eligible=certs,
            compliance_score=round(max(0.0, score), 1),
            digital_signature_hash=sig_hash,
            qr_payload=qr_payload,
        )

    def audit_compliance(self, farm: FarmDigitalTwin) -> VietGAPAuditReport:
        """Run complete farm-wide food safety and traceability audit."""
        now = time.time()
        ready_count = 0
        quarantine_count = 0
        advisories: list[str] = []

        for z in farm.zones:
            cleared, remaining_h, active = self.check_zone_phi(z.id, now)
            if cleared:
                ready_count += 1
            else:
                quarantine_count += 1
                advisories.append(f"Zone {z.id} under PHI quarantine for {remaining_h}h ({', '.join(active)})")

        water_ok = self.water_safety.is_compliant
        zone_total = len(farm.zones) or 1
        phi_clean_ratio = ready_count / zone_total

        audit_score = round((phi_clean_ratio * 60.0) + (40.0 if water_ok else 0.0), 1)

        if audit_score >= 95.0:
            tier = "AAA_EXPORT_READY"
        elif audit_score >= 80.0:
            tier = "AA_DOMESTIC_PREMIUM"
        elif audit_score >= 60.0:
            tier = "A_STANDARD"
        else:
            tier = "NON_COMPLIANT"

        return VietGAPAuditReport(
            farm_id=farm.farm_id,
            audit_timestamp_utc=datetime.now(UTC).isoformat(),
            overall_compliance_score=audit_score,
            compliance_tier=tier,
            water_safety_passed=water_ok,
            active_treatments_count=len(self._application_logs),
            zones_ready_for_harvest_count=ready_count,
            zones_in_phi_quarantine_count=quarantine_count,
            quarantine_advisories=advisories,
        )
