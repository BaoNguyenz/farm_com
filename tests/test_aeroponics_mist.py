"""
Unit test suite for Vertical Aeroponics Ultrasonic Misting & Nutrient Uptake Engine.
"""

from backend.core.aeroponics_mist import (
    AeroponicsMistEngine,
    AtomizerMode,
)


def test_ultrasonic_vs_high_pressure_droplet_size():
    """Verify ultrasonic piezo generates finer Sauter droplets (~15 um) than nozzles (~45 um)."""
    engine = AeroponicsMistEngine()
    d_piezo = engine.compute_droplet_diameter_um(AtomizerMode.ULTRASONIC_PIEZO_1_7MHZ)
    d_nozzle = engine.compute_droplet_diameter_um(AtomizerMode.HIGH_PRESSURE_NOZZLE_80PSI)

    assert 10.0 <= d_piezo <= 20.0
    assert d_nozzle == 45.0
    assert d_piezo < d_nozzle


def test_dissolved_oxygen_temperature_solubility():
    """Verify dissolved oxygen saturation decreases as root chamber warms."""
    engine = AeroponicsMistEngine()
    do_20 = engine.compute_mist_dissolved_oxygen(20.0)
    do_30 = engine.compute_mist_dissolved_oxygen(30.0)

    assert do_20 > 8.5
    assert do_20 > do_30


def test_michaelis_menten_ion_uptake():
    """Verify nitrate and potassium uptake follow Michaelis-Menten saturation and thermal optimum."""
    engine = AeroponicsMistEngine()
    no3_opt, k_opt = engine.compute_michaelis_menten_uptake(150.0, 200.0, 21.0)
    no3_cold, k_cold = engine.compute_michaelis_menten_uptake(150.0, 200.0, 10.0)

    assert no3_opt > no3_cold > 0.0
    assert k_opt > k_cold > 0.0


def test_adaptive_duty_cycle_and_desiccation_alarm():
    """Verify dry root chamber shortens OFF interval and flags desiccation risk."""
    engine = AeroponicsMistEngine()

    optimal = engine.evaluate_chamber(root_chamber_temp_c=21.0, root_chamber_rh_pct=94.0)
    dry = engine.evaluate_chamber(root_chamber_temp_c=23.0, root_chamber_rh_pct=75.0)

    assert optimal.chamber_status == "OPTIMAL_ULTRASONIC_MIST"
    assert optimal.root_desiccation_risk is False
    assert dry.mist_off_seconds < optimal.mist_off_seconds
    assert dry.root_desiccation_risk is True
    assert dry.chamber_status == "CRITICAL_ROOT_DESICCATION_RISK"


def test_root_heat_hypoxia_warning():
    """Verify root chamber > 26°C triggers hypoxia heat warning."""
    engine = AeroponicsMistEngine()
    hot = engine.evaluate_chamber(root_chamber_temp_c=28.0, root_chamber_rh_pct=90.0)
    assert hot.chamber_status == "WARNING_ROOT_HYPOXIA_HEAT"
