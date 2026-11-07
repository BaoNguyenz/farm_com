"""
Unit tests for Aerial Drone Multispectral Scouting & Canopy Analysis Engine.
"""

import pytest

from backend.core.drone_scouting import (
    DroneMissionStatus,
    DroneScoutingEngine,
    SpectralBandReflectance,
)
from backend.core.twin_state import create_default_farm


def test_spectral_indices_calculation():
    # Dense green crop reflectance
    bands = SpectralBandReflectance(
        blue=0.03,
        green=0.12,
        red=0.04,
        red_edge=0.25,
        nir=0.65,
    )

    indices = DroneScoutingEngine.compute_spectral_indices(bands)

    # VARI = (0.12 - 0.04) / (0.12 + 0.04 - 0.03) = 0.08 / 0.13 = 0.6154
    assert indices["vari"] == pytest.approx(0.6154, 0.01)

    # NDRE = (0.65 - 0.25) / (0.65 + 0.25) = 0.40 / 0.90 = 0.4444
    assert indices["ndre"] == pytest.approx(0.4444, 0.01)

    # NDVI = (0.65 - 0.04) / (0.65 + 0.04) = 0.61 / 0.69 = 0.8841
    assert indices["ndvi"] == pytest.approx(0.8841, 0.01)


def test_spectral_indices_zero_denominators():
    bands = SpectralBandReflectance(
        blue=0.0,
        green=0.0,
        red=0.0,
        red_edge=0.0,
        nir=0.0,
    )
    indices = DroneScoutingEngine.compute_spectral_indices(bands)
    assert indices["vari"] == 0.0
    assert indices["ndre"] == 0.0
    assert indices["ndvi"] == 0.0


def test_analyze_zone_healthy_and_diseased():
    farm = create_default_farm()
    engine = DroneScoutingEngine()

    healthy_zone = farm.zones[0]
    healthy_zone.health_status = "optimal"
    healthy_zone.ndvi = 0.82

    survey_healthy = engine.analyze_zone(healthy_zone)
    assert survey_healthy.canopy_cover_pct >= 80.0
    assert survey_healthy.chlorosis_hotspots == 0
    assert survey_healthy.scouting_urgency in ("nominal", "warning")

    # Diseased zone with low NDRE/chlorosis
    diseased_zone = farm.zones[1]
    diseased_zone.health_status = "diseased"
    diseased_zone.ndvi = 0.35

    survey_diseased = engine.analyze_zone(diseased_zone)
    assert survey_diseased.scouting_urgency == "critical"
    assert "CRITICAL" in survey_diseased.actionable_finding


def test_simulate_mission_success():
    farm = create_default_farm()
    engine = DroneScoutingEngine()

    zones = farm.zones
    report = engine.simulate_mission(
        zones=zones,
        mission_id="MISSION-TEST-42",
        altitude_m=35.0,
        initial_battery_pct=90.0,
    )

    assert report.mission_id == "MISSION-TEST-42"
    assert report.status == DroneMissionStatus.COMPLETED
    assert report.flight_altitude_m == 35.0
    assert report.total_area_scouted_ha > 0.0
    assert report.flight_duration_minutes > 0.0
    assert report.battery_consumed_pct > 0.0
    assert len(report.zone_surveys) == len(zones)


def test_simulate_mission_low_battery_abort():
    farm = create_default_farm()
    engine = DroneScoutingEngine()

    # Farm is 0.04 ha -> consumes ~0.18% battery.
    # Starting with 20.1% battery leaves < 20.0% safety reserve -> ABORT
    zones = farm.zones
    report = engine.simulate_mission(
        zones=zones,
        mission_id="MISSION-ABORT-LOWBAT",
        initial_battery_pct=20.1,
    )

    assert report.status == DroneMissionStatus.ABORTED_LOW_BATTERY
