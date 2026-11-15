"""
Unit test suite for Greenhouse CEA Microclimate & Photosynthetic CO2 Kinetics.
"""
from backend.core.greenhouse_cea import GreenhouseCEAEngine


def test_calculate_vpd() -> None:
    # 25°C and 60% RH
    vpd_moderate = GreenhouseCEAEngine.calculate_vpd(temp_c=25.0, humidity_percent=60.0)
    assert 1.10 <= vpd_moderate <= 1.40

    # 18°C and 95% RH (near saturation)
    vpd_humid = GreenhouseCEAEngine.calculate_vpd(temp_c=18.0, humidity_percent=95.0)
    assert vpd_humid < 0.20


def test_calculate_photosynthesis_dark_and_light() -> None:
    engine = GreenhouseCEAEngine()

    # Dark conditions (night)
    pn_dark = engine.calculate_photosynthesis(par_umol_m2_s=0.0, co2_ppm=420.0, temp_c=20.0)
    assert pn_dark == -1.5

    # Optimal daylight with ambient CO2
    pn_ambient = engine.calculate_photosynthesis(par_umol_m2_s=600.0, co2_ppm=420.0, temp_c=24.0)
    assert pn_ambient > 8.0

    # Optimal daylight with enriched CO2 (850 ppm)
    pn_enriched = engine.calculate_photosynthesis(par_umol_m2_s=600.0, co2_ppm=850.0, temp_c=24.0)
    assert pn_enriched > pn_ambient


def test_regulate_microclimate_mild_and_enrichment() -> None:
    engine = GreenhouseCEAEngine()

    # Mild day: 21°C ambient, 14 MJ solar radiation
    micro = engine.regulate_microclimate(
        ambient_temp_c=21.0,
        ambient_humidity_pct=65.0,
        solar_radiation_mj=14.0,
        target_temp_c=24.0,
        target_co2_ppm=850.0,
    )

    assert micro.greenhouse_id == "GH-POLYHOUSE-01"
    assert micro.actuators.roof_vent_pct < 55.0
    assert micro.actuators.co2_dosing_valve_open is True
    assert micro.co2_concentration_ppm >= 800.0
    assert micro.canopy_net_photosynthesis_umol_m2_s > 5.0


def test_regulate_microclimate_heat_ventilation_override() -> None:
    engine = GreenhouseCEAEngine()

    # Hot sunny midday: 32°C ambient, 24 MJ solar radiation
    micro = engine.regulate_microclimate(
        ambient_temp_c=32.0,
        ambient_humidity_pct=50.0,
        solar_radiation_mj=24.0,
        target_temp_c=24.0,
        target_co2_ppm=850.0,
    )

    assert micro.actuators.roof_vent_pct >= 80.0
    assert micro.actuators.pad_and_fan_active is True
    # Anti-exhaust loss rule: CO2 injection must be shut down when vents are wide open
    assert micro.actuators.co2_dosing_valve_open is False
    assert micro.actuators.co2_dosing_rate_kg_h == 0.0
