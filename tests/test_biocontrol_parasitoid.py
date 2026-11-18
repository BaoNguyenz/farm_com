"""
Unit test suite for parasitoid wasp dynamics and whitefly biological suppression.
"""
import pytest

from backend.core.biocontrol_parasitoid import (
    ParasitoidBioParams,
    ParasitoidKineticsEngine,
    ParasitoidSpecies,
    WhiteflyColonyState,
)


def test_pupal_duration_thermal_time():
    """Verify that higher temperature accelerates pupal emergence."""
    params = ParasitoidBioParams(
        base_temp_c=12.5,
        degree_days_to_emerge=140.0,
    )
    # At 24C: effective temp = 11.5, duration = 140 / 11.5 = 12.17 days
    duration_warm = ParasitoidKineticsEngine.calculate_pupal_duration_days(24.0, params)
    # At 18C: effective temp = 5.5, duration = 140 / 5.5 = 25.45 days
    duration_cool = ParasitoidKineticsEngine.calculate_pupal_duration_days(18.0, params)

    assert duration_warm < duration_cool
    assert pytest.approx(duration_warm, abs=0.5) == 12.2
    assert pytest.approx(duration_cool, abs=0.5) == 25.5


def test_nicholson_bailey_parasitism_and_feeding():
    """Verify functional response of parasitoid oviposition and host-feeding."""
    params = ParasitoidKineticsEngine.SPECIES_PARAMS[ParasitoidSpecies.ENCARSIA_FORMOSA]

    # Zero condition
    p0, f0 = ParasitoidKineticsEngine.calculate_parasitism_and_feeding(0.0, 2.0, params)
    assert p0 == 0.0 and f0 == 0.0

    p_no_wasp, f_no_wasp = ParasitoidKineticsEngine.calculate_parasitism_and_feeding(20.0, 0.0, params)
    assert p_no_wasp == 0.0 and f_no_wasp == 0.0

    # Normal conditions
    parasitized, feeding = ParasitoidKineticsEngine.calculate_parasitism_and_feeding(20.0, 2.0, params)
    assert parasitized > 0.0
    assert feeding > 0.0
    assert (parasitized + feeding) < 20.0
    # Host feeding is ~22% of total attacked
    total_attacked = parasitized + feeding
    assert pytest.approx(feeding / total_attacked, rel=0.05) == 0.22


def test_single_step_wasp_emergence_and_state():
    """Test single step simulation with emergence from black scales."""
    initial_state = WhiteflyColonyState(
        day=0.0,
        healthy_nymphs=15.0,
        parasitized_pupae=10.0,
        adult_wasps=1.5,
    )

    next_state = ParasitoidKineticsEngine.simulate_step(
        state=initial_state,
        temp_c=25.0,
        dt_days=1.0,
    )

    assert next_state.day == 1.0
    assert next_state.daily_parasitized > 0.0
    assert next_state.daily_host_feeding_kills > 0.0
    assert next_state.daily_emerged_wasps > 0.0
    assert next_state.parasitism_rate_pct > 0.0


def test_card_release_dose_calculation():
    """Test cardboard release tag dosage for Encarsia formosa."""
    # Preventive: nymph density 2.0 <= ET (3.0)
    dose_prev = ParasitoidKineticsEngine.calculate_card_release_dose(
        canopy_area_m2=500.0,
        nymph_density_per_leaf=2.0,
        economic_threshold=3.0,
        pupae_per_card=60,
    )
    assert dose_prev["strategy"] == "preventive"
    assert dose_prev["wasps_per_m2"] == 1.5
    assert dose_prev["total_cards_recommended"] == 13  # ceil(750 / 60) = 13

    # Curative heavy: nymph density 10.0 > 2 * ET
    dose_cur = ParasitoidKineticsEngine.calculate_card_release_dose(
        canopy_area_m2=500.0,
        nymph_density_per_leaf=10.0,
        economic_threshold=3.0,
        pupae_per_card=60,
    )
    assert dose_cur["strategy"] == "curative_heavy"
    assert dose_cur["wasps_per_m2"] == 6.5
    assert dose_cur["total_cards_recommended"] == 55  # ceil(3250 / 60) = 55


def test_multi_step_parasitoid_control():
    """Verify parasitoid cohort increases parasitism over multi-day period."""
    state = WhiteflyColonyState(
        day=0.0,
        healthy_nymphs=12.0,
        parasitized_pupae=8.0,
        adult_wasps=2.0,
    )

    for _ in range(8):
        state = ParasitoidKineticsEngine.simulate_step(state=state, temp_c=24.0, dt_days=1.0)

    assert state.day == 8.0
    # Parasitism rate should be established
    assert state.parasitism_rate_pct >= 40.0
    assert state.parasitoid_status in ["satisfactory", "optimal_control"]
