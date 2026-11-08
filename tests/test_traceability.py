"""
Unit tests for VietGAP & GlobalGAP Food Safety, PHI Residue & Batch Traceability Engine.
"""

from backend.core.traceability import (
    ChemicalApplicationRecord,
    TraceabilityEngine,
    WaterSafetyProfile,
)
from backend.core.twin_state import create_default_farm


def test_chemical_application_record_phi_clearance():
    base_time = 1700000000.0

    # 7-day PHI requirement
    record = ChemicalApplicationRecord(
        treatment_id="TRT-001",
        zone_id="Z_0_0",
        substance_name="Copper Hydroxide",
        substance_type="copper_chelate",
        application_timestamp=base_time,
        phi_days_required=7.0,
        dosage_per_ha=2.5,
    )

    # 3 days later -> NOT cleared
    assert record.days_elapsed(base_time + 3.0 * 86400.0) == 3.0
    assert record.is_cleared_for_harvest(base_time + 3.0 * 86400.0) is False

    # 7.5 days later -> CLEARED
    assert record.days_elapsed(base_time + 7.5 * 86400.0) == 7.5
    assert record.is_cleared_for_harvest(base_time + 7.5 * 86400.0) is True


def test_water_safety_profile_compliance():
    # Compliant water
    good_water = WaterSafetyProfile(
        e_coli_cfu_per_100ml=20.0,
        total_coliform_cfu_per_100ml=350.0,
        lead_pb_ppm=0.01,
        cadmium_cd_ppm=0.002,
        arsenic_as_ppm=0.01,
    )
    assert good_water.is_compliant is True

    # High E. coli contamination (> 100 CFU)
    bad_water = WaterSafetyProfile(
        e_coli_cfu_per_100ml=150.0,
        total_coliform_cfu_per_100ml=350.0,
    )
    assert bad_water.is_compliant is False


def test_traceability_engine_phi_quarantine_and_clearance():
    engine = TraceabilityEngine()
    current_time = 1700000000.0

    # Zone Z_0_0 has active treatment applied 2 days ago (PHI = 7 days)
    engine.log_treatment(
        zone_id="Z_0_0",
        substance_name="Copper Hydroxide",
        substance_type="copper_chelate",
        phi_days=7.0,
        timestamp=current_time - (2.0 * 86400.0),
    )

    cleared, remaining_hours, active = engine.check_zone_phi("Z_0_0", current_time=current_time)
    assert cleared is False
    assert remaining_hours > 0.0
    # 5 days remaining = ~120 hours
    assert 118.0 <= remaining_hours <= 122.0
    assert len(active) == 1

    # Zone Z_0_1 has no treatments -> instantly cleared
    cleared_clean, rem_clean, _ = engine.check_zone_phi("Z_0_1", current_time=current_time)
    assert cleared_clean is True
    assert rem_clean == 0.0


def test_traceability_batch_passport_minting():
    engine = TraceabilityEngine()
    farm = create_default_farm()
    zone = farm.zones[0]

    passport = engine.generate_batch_passport(
        farm_id=farm.farm_id,
        zone=zone,
        weight_kg=125.0,
    )

    assert passport.farm_id == farm.farm_id
    assert passport.zone_id == zone.id
    assert passport.weight_kg == 125.0
    assert passport.phi_clearance is True
    assert passport.compliance_score >= 90.0
    assert len(passport.certifications_eligible) > 0
    assert len(passport.digital_signature_hash) == 64  # SHA-256
    assert "https://trace.farm.vn/verify/" in passport.qr_payload


def test_traceability_farm_audit():
    engine = TraceabilityEngine()
    farm = create_default_farm()

    # Log treatment on 1 zone
    engine.log_treatment(
        zone_id=farm.zones[0].id,
        substance_name="Azoxystrobin",
        phi_days=14.0,
    )

    audit = engine.audit_compliance(farm)
    assert audit.farm_id == farm.farm_id
    assert audit.overall_compliance_score > 70.0
    assert audit.zones_ready_for_harvest_count == len(farm.zones) - 1
    assert audit.zones_in_phi_quarantine_count == 1
    assert len(audit.quarantine_advisories) == 1
