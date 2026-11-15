"""
Unit test suite for Bio-Acoustic Pollinator Monitoring and Buzz Frequency Analysis.
"""
from backend.core.pollination import BioAcousticPollinationEngine
from backend.core.twin_state import create_default_farm


def test_analyze_acoustic_signature() -> None:
    engine = BioAcousticPollinationEngine()

    # Legitimate bumblebee sonication buzz (345 Hz, 1.5s)
    assert engine.analyze_acoustic_signature(frequency_hz=345.0, duration_seconds=1.5) is True

    # Regular flight wingbeat (180 Hz)
    assert engine.analyze_acoustic_signature(frequency_hz=180.0, duration_seconds=1.5) is False

    # Transient electrical noise spike (345 Hz, 0.02s)
    assert engine.analyze_acoustic_signature(frequency_hz=345.0, duration_seconds=0.02) is False


def test_audit_zone_optimal_pollination() -> None:
    engine = BioAcousticPollinationEngine()

    audit = engine.audit_zone(
        zone_id="Z_0_0",
        flower_count_per_m2=40,
        buzz_events_per_hour=140,
        ambient_temp_c=22.5,
    )

    assert audit.zone_id == "Z_0_0"
    assert audit.visitations_per_flower >= 2.5
    assert audit.pollination_status == "optimal"
    assert audit.fruit_deformation_risk_pct < 10.0
    assert audit.foraging_thermal_stress is False


def test_audit_zone_deficient_pollination() -> None:
    engine = BioAcousticPollinationEngine()

    audit = engine.audit_zone(
        zone_id="Z_1_1",
        flower_count_per_m2=50,
        buzz_events_per_hour=30,
        ambient_temp_c=22.0,
    )

    assert audit.visitations_per_flower < 1.0
    assert audit.pollination_status in ("deficient", "severe_deficit")
    assert audit.fruit_deformation_risk_pct > 40.0
    assert "bumblebee" in audit.recommended_action.lower()


def test_audit_zone_thermal_cessation() -> None:
    engine = BioAcousticPollinationEngine()

    # Extreme afternoon heat inside polyhouse (35°C)
    audit = engine.audit_zone(
        zone_id="Z_0_2",
        flower_count_per_m2=40,
        buzz_events_per_hour=150,
        ambient_temp_c=35.0,
    )

    assert audit.foraging_thermal_stress is True
    assert audit.buzz_events_count_per_hour == 0
    assert "THERMAL FORAGING CESSATION" in audit.recommended_action


def test_audit_farm_consolidation() -> None:
    engine = BioAcousticPollinationEngine()
    farm = create_default_farm()

    report = engine.audit_farm(farm)

    assert report.farm_id == farm.farm_id
    assert report.average_visitations_per_flower > 0.0
    assert report.overall_fruit_set_quality_pct > 50.0
    assert len(report.zone_audits) == len(farm.zones)
