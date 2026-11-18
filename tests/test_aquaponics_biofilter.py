"""
Unit test suite for two-stage MBBR biofilter nitrification kinetics and alkalinity destruction.
"""
import pytest

from backend.core.aquaponics_biofilter import (
    BiofilterMediaType,
    MBBRBiofilterEngine,
)


def test_active_surface_area_k1_media():
    """Verify surface area calculation for fluidised biomedia."""
    # 0.75 m3 of K1 media (800 m2/m3) -> 600.0 m2
    area_k1 = MBBRBiofilterEngine.calculate_active_surface_area(0.75, BiofilterMediaType.K1_CARRIER)
    assert area_k1 == 600.0

    # 1.0 m3 of K3 media (500 m2/m3) -> 500.0 m2
    area_k3 = MBBRBiofilterEngine.calculate_active_surface_area(1.0, BiofilterMediaType.K3_CARRIER)
    assert area_k3 == 500.0


def test_environmental_scaling_temperature_and_ph():
    """Verify performance scaling factors across temperature and pH."""
    # Optimal conditions: 25C, pH 7.2 -> ~1.0
    opt = MBBRBiofilterEngine.calculate_environmental_multiplier(temp_c=25.0, ph=7.2)
    assert pytest.approx(opt, abs=0.05) == 1.0

    # Cold conditions (10C) -> severe slowdown
    cold = MBBRBiofilterEngine.calculate_environmental_multiplier(temp_c=10.0, ph=7.2)
    assert cold < 0.2

    # Acidic water (pH 5.5) -> nitrification halted / severely suppressed
    acidic = MBBRBiofilterEngine.calculate_environmental_multiplier(temp_c=25.0, ph=5.5)
    assert acidic < 0.2


def test_two_stage_nitrification_step():
    """Verify oxidation of TAN -> NO2 -> NO3 in a single biofilter pass."""
    state = MBBRBiofilterEngine.simulate_biofilter_step(
        inlet_tan_mg_l=1.20,
        inlet_no2_mg_l=0.15,
        inlet_no3_mg_l=15.0,
        dissolved_oxygen_mg_l=6.5,
        water_flow_m3_h=3.5,
        media_volume_m3=0.75,
        media_type=BiofilterMediaType.K1_CARRIER,
        ph=7.2,
        temp_c=26.0,
        dt_hours=1.0,
    )

    # Outlet TAN should be reduced significantly
    assert state.outlet_tan_mg_l < state.inlet_tan_mg_l
    # Nitrate should increase
    assert state.outlet_no3_mg_l > state.inlet_no3_mg_l
    # Oxidation rates positive
    assert state.tan_oxidation_rate_g_h > 0.0
    assert state.no2_oxidation_rate_g_h > 0.0
    assert state.tan_conversion_efficiency_pct > 70.0


def test_stoichiometric_oxygen_consumption():
    """Verify oxygen consumption matches ~4.57 g O2 per g TAN fully nitrified."""
    state = MBBRBiofilterEngine.simulate_biofilter_step(
        inlet_tan_mg_l=1.0,
        inlet_no2_mg_l=0.0,
        inlet_no3_mg_l=0.0,
        dissolved_oxygen_mg_l=7.0,
        water_flow_m3_h=2.0,
        media_volume_m3=1.0,
        ph=7.4,
        temp_c=25.0,
        dt_hours=1.0,
    )

    # If TAN is fully oxidized to NO3, O2 consumed = (3.43 * tan_ox) + (1.14 * no2_ox)
    expected_o2 = (3.43 * state.tan_oxidation_rate_g_h) + (1.14 * state.no2_oxidation_rate_g_h)
    assert pytest.approx(state.oxygen_consumed_g_h, abs=0.1) == expected_o2


def test_alkalinity_destruction():
    """Verify alkalinity destruction follows 7.14 g CaCO3 per g TAN oxidized."""
    state = MBBRBiofilterEngine.simulate_biofilter_step(
        inlet_tan_mg_l=1.5,
        inlet_no2_mg_l=0.0,
        inlet_no3_mg_l=10.0,
        dissolved_oxygen_mg_l=6.5,
        water_flow_m3_h=3.0,
        ph=7.2,
        temp_c=25.0,
    )

    expected_alk = 7.14 * state.tan_oxidation_rate_g_h
    assert pytest.approx(state.alkalinity_destroyed_g_h_caco3, abs=0.1) == expected_alk


def test_do_inhibition_low_oxygen():
    """Verify DO inhibition flag when biofilter aeration drops below 4.0 mg/L."""
    # Under high load (8.0 mg/L TAN) and compact media volume (0.15 m3)
    state_hypoxic = MBBRBiofilterEngine.simulate_biofilter_step(
        inlet_tan_mg_l=8.0,
        inlet_no2_mg_l=0.5,
        inlet_no3_mg_l=10.0,
        dissolved_oxygen_mg_l=0.5,  # Severely hypoxic biofilter
        water_flow_m3_h=3.0,
        media_volume_m3=0.15,
    )

    assert state_hypoxic.is_do_inhibited is True

    state_aerated = MBBRBiofilterEngine.simulate_biofilter_step(
        inlet_tan_mg_l=8.0,
        inlet_no2_mg_l=0.5,
        inlet_no3_mg_l=10.0,
        dissolved_oxygen_mg_l=7.5,  # Well aerated
        water_flow_m3_h=3.0,
        media_volume_m3=0.15,
    )

    assert state_aerated.is_do_inhibited is False
    assert state_aerated.tan_conversion_efficiency_pct > state_hypoxic.tan_conversion_efficiency_pct
