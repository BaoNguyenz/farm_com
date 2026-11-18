"""
Unit test suite for macro-biologic spatial release planning and drone aerial dispersion.
"""
import pytest

from backend.core.biocontrol import PredatorSpecies, PreySpecies
from backend.core.biocontrol_dispersion import (
    CarrierMaterial,
    DispersionMethod,
    MacroBiologicDispersionEngine,
)


def test_dose_rate_escalation():
    """Verify dose per m2 scales with pest scouting density."""
    # Low / below ET
    assert MacroBiologicDispersionEngine.calculate_dose_rate(2.0, economic_threshold=5.0) == 2.5
    # Moderate / between ET and EIL
    assert MacroBiologicDispersionEngine.calculate_dose_rate(8.0, economic_threshold=5.0, economic_injury_level=15.0) == 12.0
    # Outbreak / above EIL
    assert MacroBiologicDispersionEngine.calculate_dose_rate(22.0, economic_threshold=5.0, economic_injury_level=15.0) == 28.0


def test_plan_zone_release_drone_hopper():
    """Verify drone aerial hopper dispersion parameters."""
    canopy_m2 = 600.0
    pest_density = 18.0  # Outbreak -> 28 mites/m2

    plan = MacroBiologicDispersionEngine.plan_zone_release(
        zone_id="ZONE_STRAWBERRY_B",
        canopy_area_m2=canopy_m2,
        pest_density=pest_density,
        target_pest=PreySpecies.TWO_SPOTTED_SPIDER_MITE,
        beneficial_species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
        use_drone=True,
        flight_speed_m_s=1.5,
        swath_width_m=2.0,
    )

    assert plan.zone_id == "ZONE_STRAWBERRY_B"
    assert plan.dispersion_method == DispersionMethod.DRONE_AERIAL_HOPPER
    assert plan.dose_per_m2 == 28.0
    assert plan.total_beneficials_needed == int(600.0 * 28.0)  # 16,800 mites
    # Bottle packs: 16,800 / 2,000 = ceil(8.4) = 9 bottles
    assert plan.packages_required == 9
    assert plan.total_cost_vnd == 9 * 350000.0  # 3,150,000 VND
    # Drone flow rate: coverage = 1.5 * 2.0 = 3.0 m2/s. 28 * 3.0 = 84 mites/sec
    assert pytest.approx(plan.drone_hopper_flow_rate_per_sec, abs=0.1) == 84.0
    # Flight duration: 600 m2 / 3 m2/s = 200 seconds = 3.33 minutes
    assert pytest.approx(plan.application_duration_minutes, abs=0.1) == 3.3


def test_plan_zone_release_manual_shaker():
    """Verify manual shaker method calculates realistic labor duration."""
    plan = MacroBiologicDispersionEngine.plan_zone_release(
        zone_id="ZONE_GREENHOUSE_C",
        canopy_area_m2=400.0,
        pest_density=3.0,  # Preventive
        use_drone=False,
    )

    assert plan.dispersion_method == DispersionMethod.MANUAL_SHAKER
    assert plan.drone_hopper_flow_rate_per_sec == 0.0
    assert plan.application_duration_minutes == 8.0  # 400 m2 / 50 m2/min = 8.0 min


def test_farm_manifest_aggregation():
    """Verify multi-zone aggregation in FarmReleaseManifest."""
    specs = [
        {"zone_id": "BAY_1", "canopy_area_m2": 500.0, "pest_density": 4.0},  # 2.5 * 500 = 1250 mites -> 1 bottle
        {"zone_id": "BAY_2", "canopy_area_m2": 800.0, "pest_density": 10.0},  # 12.0 * 800 = 9600 mites -> 5 bottles
    ]

    manifest = MacroBiologicDispersionEngine.generate_farm_manifest(specs, manifest_id="TEST_MANIFEST_01")

    assert manifest.manifest_id == "TEST_MANIFEST_01"
    assert manifest.total_zones == 2
    assert manifest.total_canopy_area_m2 == 1300.0
    assert manifest.total_beneficials_dispatched == 1250 + 9600
    assert manifest.total_packages_needed == 1 + 5
    assert manifest.total_estimated_cost_vnd == 6 * 350000.0


def test_amblyseius_swirskii_bulk_pack():
    """Verify Amblyseius swirskii packaging spec (25,000 mites / sawdust)."""
    plan = MacroBiologicDispersionEngine.plan_zone_release(
        zone_id="ZONE_PEPPER_A",
        canopy_area_m2=1000.0,
        pest_density=12.0,  # 12.0 * 1000 = 12,000 mites
        beneficial_species=PredatorSpecies.AMBLYSEIUS_SWIRSKII,
    )

    assert plan.beneficial_species == PredatorSpecies.AMBLYSEIUS_SWIRSKII
    # 12,000 mites fits in 1 bulk 25k bottle
    assert plan.packages_required == 1
    assert plan.total_cost_vnd == 680000.0
    pkg = MacroBiologicDispersionEngine.DEFAULT_PACKAGING[PredatorSpecies.AMBLYSEIUS_SWIRSKII]
    assert pkg.carrier == CarrierMaterial.SAWDUST
