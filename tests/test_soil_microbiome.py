"""
Unit tests for Soil Microbiome Ecology, Nitrogen Leaching & Root Hypoxia Engine.
"""

from backend.core.soil_microbiome import (
    MicrobialPopulationProfile,
    SoilMicrobiomeEngine,
)
from backend.core.twin_state import create_default_farm


def test_microbial_population_profile_defaults():
    profile = MicrobialPopulationProfile()
    assert profile.beneficial_bacteria_cfu_per_g >= 1e7
    assert profile.mycorrhizae_colonization_pct >= 50.0
    assert profile.soil_organic_matter_pct > 3.0
    assert profile.trichoderma_cfu_per_g > 1e5


def test_audit_zone_optimal_moisture_nominal_leaching():
    engine = SoilMicrobiomeEngine()
    farm = create_default_farm()
    zone = farm.zones[0]
    zone.soil_moisture_pct = 62.0  # Under 68% field capacity

    audit = engine.audit_zone(zone, percolation_hours=1.0)
    assert audit.leaching_risk_tier == "minimal"
    assert audit.estimated_leached_n_kg_ha == 0.0
    assert audit.root_hypoxia_index == 0.0
    assert audit.soil_health_index >= 85.0
    assert audit.reinoculation_recommended is False


def test_audit_zone_saturation_hypoxia_and_critical_leaching():
    engine = SoilMicrobiomeEngine()
    farm = create_default_farm()
    zone = farm.zones[1]
    zone.soil_moisture_pct = 92.0  # Above 82% saturation

    audit = engine.audit_zone(zone, percolation_hours=2.0)
    assert audit.leaching_risk_tier == "critical_leaching"
    assert audit.estimated_leached_n_kg_ha > 0.5
    assert audit.root_hypoxia_index > 0.4
    assert audit.soil_health_index < 70.0
    assert audit.reinoculation_recommended is True
    assert "aerate" in audit.recommended_bio_treatment.lower() or "trichoderma" in audit.recommended_bio_treatment.lower()


def test_audit_farm_consolidation():
    engine = SoilMicrobiomeEngine()
    farm = create_default_farm()

    # Inject flood in one zone
    farm.zones[0].soil_moisture_pct = 90.0

    report = engine.audit_farm(farm, percolation_hours=1.0)
    assert report.farm_id == farm.farm_id
    assert 0.0 <= report.average_soil_health_index <= 100.0
    assert len(report.zone_audits) == len(farm.zones)
    assert report.zones_with_hypoxia_risk_count >= 1
    assert report.zones_with_leaching_risk_count >= 1
    assert report.total_estimated_leached_n_kg > 0.0
