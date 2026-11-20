"""
Unit tests for Precision Fertigation Dosing & Solute Transport Engine.
"""

from backend.core.fertigation_solute import (
    FertigationMixResult,
    FertigationRecipe,
    FertigationSoluteEngine,
)


def test_recipe_targets_compliance() -> None:
    engine = FertigationSoluteEngine()

    result = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.FRUITING,
        irrigation_flow_rate_lph=2000.0,
    )

    assert isinstance(result, FertigationMixResult)
    assert result.recipe == FertigationRecipe.FRUITING
    assert result.target_ec_ms_cm == 2.40
    assert result.target_ph == 6.05
    assert result.potassium_ppm == 280.0
    assert result.calcium_ppm == 140.0
    assert abs(result.measured_ec_ms_cm - 2.40) < 0.25


def test_pid_injection_rate_scaling_with_flow() -> None:
    engine = FertigationSoluteEngine()

    res_1k = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.VEGETATIVE,
        irrigation_flow_rate_lph=1000.0,
    )
    res_2k = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.VEGETATIVE,
        irrigation_flow_rate_lph=2000.0,
    )

    # Double irrigation flow should roughly double stock injection rates
    assert abs(res_2k.stock_a_injection_lph - (res_1k.stock_a_injection_lph * 2.0)) < 0.05
    assert abs(res_2k.stock_b_injection_lph - (res_1k.stock_b_injection_lph * 2.0)) < 0.05


def test_ph_acid_neutralization_response() -> None:
    engine = FertigationSoluteEngine()

    # Raw water at high pH 7.8 vs normalized pH 6.0
    res_high_ph = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.VEGETATIVE,
        irrigation_flow_rate_lph=1500.0,
        measured_ph=7.80,
    )
    res_norm_ph = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.VEGETATIVE,
        irrigation_flow_rate_lph=1500.0,
        measured_ph=5.85,
    )

    # High pH requires active acid injection; normalized requires near zero acid
    assert res_high_ph.acid_c_injection_lph > res_norm_ph.acid_c_injection_lph
    assert res_high_ph.acid_c_injection_lph > 0.5
    assert res_norm_ph.acid_c_injection_lph == 0.0


def test_leaching_fraction_and_salinity_hazard() -> None:
    engine = FertigationSoluteEngine()

    # Standard vegetative vs extreme fruiting recipe
    res_veg = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.VEGETATIVE,
        irrigation_flow_rate_lph=1000.0,
    )
    assert 5.0 <= res_veg.leaching_fraction_pct <= 25.0
    assert not res_veg.salinity_hazard_warning


def test_1d_solute_advection_dispersion_profile() -> None:
    engine = FertigationSoluteEngine()

    # Solute profile after 3 hours of irrigation
    profile = engine.simulate_1d_solute_transport(
        surface_ec=2.40,
        soil_depth_cm=60.0,
        pore_water_velocity_cm_h=3.0,
        elapsed_hours=3.0,
        dispersion_coeff_cm2_h=1.5,
    )

    assert len(profile) == 6
    # Surface depth (0cm) should have highest EC close to surface EC
    assert profile[0].depth_cm == 0.0
    assert profile[0].solute_ec_ms_cm >= 2.0
    # Deepest depth (60cm) should still be close to background EC
    assert profile[-1].depth_cm == 60.0
    assert profile[-1].solute_ec_ms_cm < profile[0].solute_ec_ms_cm


def test_closed_loop_feedback_trimming() -> None:
    engine = FertigationSoluteEngine()

    # When measured EC is deficient (1.2 vs 2.1 target), controller should boost stock injection
    res_deficient = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.FLOWERING,
        irrigation_flow_rate_lph=1000.0,
        measured_ec=1.20,
    )
    res_target = engine.compute_pid_injection_rates(
        target_recipe=FertigationRecipe.FLOWERING,
        irrigation_flow_rate_lph=1000.0,
        measured_ec=2.10,
    )

    assert res_deficient.stock_a_injection_lph > res_target.stock_a_injection_lph
