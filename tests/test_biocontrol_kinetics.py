"""
Unit test suite for Holling Type II predator-prey functional response and population kinetics.
"""
import pytest

from backend.core.biocontrol import (
    BiocontrolKineticsEngine,
    PopulationState,
    PredatorBioParameters,
    PredatorSpecies,
    PreyBioParameters,
    PreySpecies,
)


def test_holling_type_ii_saturation():
    """Verify that Holling Type II functional response saturates as prey density increases."""
    attack_rate = 0.15
    handling_time = 0.04  # Theoretical max consumption per predator = 1 / Th = 25 prey/day
    predator_p = 1.0

    # Low prey density
    c_low = BiocontrolKineticsEngine.calculate_holling_type_ii_predation(
        prey_n=2.0, predator_p=predator_p, attack_rate=attack_rate, handling_time=handling_time
    )
    # Medium prey density
    c_med = BiocontrolKineticsEngine.calculate_holling_type_ii_predation(
        prey_n=20.0, predator_p=predator_p, attack_rate=attack_rate, handling_time=handling_time
    )
    # Extremely high prey density
    c_high = BiocontrolKineticsEngine.calculate_holling_type_ii_predation(
        prey_n=100000.0, predator_p=predator_p, attack_rate=attack_rate, handling_time=handling_time
    )

    assert c_low < c_med < c_high
    # Should approach 1 / Th = 25.0
    assert pytest.approx(c_high, rel=0.01) == 25.0


def test_temperature_scaling_curve():
    """Verify temperature-dependent activity scaling."""
    # Optimum at 25C
    assert BiocontrolKineticsEngine.temperature_scaling(25.0, t_opt_min=22.0, t_opt_max=28.0) == 1.0
    # Boundary optimum at 22C and 28C
    assert BiocontrolKineticsEngine.temperature_scaling(22.0, t_opt_min=22.0, t_opt_max=28.0) == 1.0
    assert BiocontrolKineticsEngine.temperature_scaling(28.0, t_opt_min=22.0, t_opt_max=28.0) == 1.0
    # Extreme cold (10C)
    assert BiocontrolKineticsEngine.temperature_scaling(10.0) == 0.05
    # Extreme heat (40C)
    assert BiocontrolKineticsEngine.temperature_scaling(40.0) == 0.05
    # Intermediate ramp (17C)
    ramp_cold = BiocontrolKineticsEngine.temperature_scaling(17.0, t_min=12.0, t_opt_min=22.0)
    assert 0.05 < ramp_cold < 1.0


def test_zero_prey_or_predator_behavior():
    """Verify behavior under zero boundary conditions."""
    # Zero prey -> consumption is 0
    c0 = BiocontrolKineticsEngine.calculate_holling_type_ii_predation(
        prey_n=0.0, predator_p=5.0, attack_rate=0.1, handling_time=0.05
    )
    assert c0 == 0.0

    # Zero predators -> consumption is 0
    c1 = BiocontrolKineticsEngine.calculate_holling_type_ii_predation(
        prey_n=20.0, predator_p=0.0, attack_rate=0.1, handling_time=0.05
    )
    assert c1 == 0.0


def test_single_step_rk2_starvation_and_growth():
    """Test single step RK2 integration with starvation vs active feeding."""
    pred_params = PredatorBioParameters()
    prey_params = PreyBioParameters()

    # Case A: Starvation (prey = 0)
    starving_state = PopulationState(
        day=0.0,
        prey_density=0.0,
        predator_density=10.0,
    )
    next_starving = BiocontrolKineticsEngine.simulate_step(
        current_state=starving_state,
        predator_params=pred_params,
        prey_params=prey_params,
        temp_c=25.0,
        dt_days=1.0,
    )
    assert next_starving.predator_density < 10.0
    assert next_starving.prey_density == 0.0
    assert next_starving.suppression_status == "eradicated"

    # Case B: Heavy infestation outbreak
    outbreak_state = PopulationState(
        day=0.0,
        prey_density=25.0,  # > EIL (15)
        predator_density=2.0,
    )
    next_outbreak = BiocontrolKineticsEngine.simulate_step(
        current_state=outbreak_state,
        predator_params=pred_params,
        prey_params=prey_params,
        temp_c=25.0,
        dt_days=0.5,
    )
    assert next_outbreak.daily_consumption > 0.0
    assert next_outbreak.suppression_status in ["alert", "outbreak_damage"]


def test_multi_day_spider_mite_suppression():
    """Simulate 14-day timeline with Phytoseiulus persimilis controlling spider mites."""
    timeline = BiocontrolKineticsEngine.simulate_timeline(
        initial_prey=25.0,
        initial_predator=4.0,
        days=12,
        temp_c=25.0,
        predator_species=PredatorSpecies.PHYTOSEIULUS_PERSIMILIS,
        prey_species=PreySpecies.TWO_SPOTTED_SPIDER_MITE,
        step_days=0.5,
    )

    assert len(timeline) == 25  # Day 0 to Day 12 at 0.5 step
    initial = timeline[0]
    final = timeline[-1]

    # Preys should be knocked down below economic threshold (5.0)
    assert final.prey_density < initial.prey_density
    assert final.prey_density < 5.0
    assert final.suppression_status in ["controlled", "eradicated"]


def test_different_predator_species_configs():
    """Verify parameters across different predator species."""
    for species in [PredatorSpecies.PHYTOSEIULUS_PERSIMILIS, PredatorSpecies.NEOSEIULUS_CALIFORNICUS, PredatorSpecies.AMBLYSEIUS_SWIRSKII]:
        timeline = BiocontrolKineticsEngine.simulate_timeline(
            initial_prey=15.0,
            initial_predator=2.0,
            days=3,
            temp_c=26.0,
            predator_species=species,
            step_days=1.0,
        )
        assert len(timeline) == 4
        assert timeline[-1].predator_density > 0.0
