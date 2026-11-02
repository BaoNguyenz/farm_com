"""
Unit tests for Microclimate Fungal Pathogen Epidemiology Engine.
Tests disease models for Botrytis cinerea, Phytophthora cactorum,
Podosphaera aphanis, and whole-farm biosecurity risk scoring.
"""

from backend.core.epidemiology import (
    EpidemiologyEngine,
    ZoneEpidemiologyProfile,
)
from backend.core.twin_state import create_default_farm


def test_botrytis_infection_kinetics():
    # Warm, humid conditions optimal for Gray Mold: 20°C, 92% RH
    risk_optimal = EpidemiologyEngine.calculate_botrytis_risk(temp_c=20.0, humidity_pct=92.0)
    assert risk_optimal.risk_score >= 65.0
    assert risk_optimal.risk_level in ("high", "critical")
    assert "Bacillus subtilis" in risk_optimal.bio_control_recommendation

    # Dry sunny conditions: 28°C, 40% RH -> No infection pressure
    risk_arid = EpidemiologyEngine.calculate_botrytis_risk(temp_c=28.0, humidity_pct=40.0)
    assert risk_arid.risk_score == 0.0
    assert risk_arid.risk_level == "low"


def test_phytophthora_waterlogging_kinetics():
    # Saturated root zone: 88% moisture, 22°C soil temp
    risk_saturated = EpidemiologyEngine.calculate_phytophthora_risk(soil_temp_c=22.0, soil_moisture_pct=88.0)
    assert risk_saturated.risk_score >= 40.0
    assert "Trichoderma" in risk_saturated.bio_control_recommendation
    assert "Veto irrigation" in risk_saturated.bio_control_recommendation

    # Well-drained soil: 45% moisture
    risk_drained = EpidemiologyEngine.calculate_phytophthora_risk(soil_temp_c=20.0, soil_moisture_pct=45.0)
    assert risk_drained.risk_score == 0.0
    assert risk_drained.risk_level == "low"


def test_powdery_mildew_kinetics():
    # Warm day with moderate humidity: 23°C, 70% RH
    risk_mildew = EpidemiologyEngine.calculate_powdery_mildew_risk(temp_c=23.0, humidity_pct=70.0)
    assert risk_mildew.risk_score >= 80.0
    assert risk_mildew.risk_level in ("high", "moderate")
    assert "potassium bicarbonate" in risk_mildew.bio_control_recommendation.lower()


def test_zone_pathogen_profile_evaluation():
    farm = create_default_farm(width=2, height=2)
    zone = farm.zones[0]
    zone.soil_moisture_pct = 85.0
    zone.soil_temp_c = 23.0
    farm.current_weather.humidity_percent = 90.0
    farm.current_weather.temp_c = 21.0

    profile = EpidemiologyEngine.evaluate_zone_pathogens(zone, farm.current_weather)
    assert isinstance(profile, ZoneEpidemiologyProfile)
    assert profile.zone_id == zone.id
    assert len(profile.pathogen_risks) == 3
    assert profile.max_risk_score > 50.0
    assert profile.biosecurity_alert_level in ("high", "critical")


def test_farm_biosecurity_audit():
    farm = create_default_farm(width=3, height=3)
    # Set high moisture to simulate post-rainstorm hazard
    for z in farm.zones:
        z.soil_moisture_pct = 86.0
        z.soil_temp_c = 22.0
    farm.current_weather.humidity_percent = 92.0
    farm.current_weather.temp_c = 20.0

    audit = EpidemiologyEngine.evaluate_farm_biosecurity(farm)
    assert audit["total_zones_monitored"] == 9
    assert audit["high_risk_zones_count"] == 9
    assert audit["average_pathogen_risk_score"] > 50.0
    assert audit["highest_threat"] is not None
