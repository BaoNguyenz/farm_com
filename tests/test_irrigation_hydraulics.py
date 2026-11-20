"""
Unit tests for Subsurface Drip Irrigation & Unsaturated Soil Hydraulics.
"""

from backend.core.irrigation_hydraulics import (
    SOIL_HYDRAULIC_CATALOG,
    SoilTextureClass,
    UnsaturatedHydraulicsEngine,
    VanGenuchtenParams,
)


def test_van_genuchten_saturation_and_residual_limits() -> None:
    engine = UnsaturatedHydraulicsEngine(SoilTextureClass.LOAM)
    params = SOIL_HYDRAULIC_CATALOG[SoilTextureClass.LOAM]

    # Effective saturation at residual water content should be 0.0
    se_res = engine.compute_effective_saturation(params.theta_r)
    assert se_res == 0.0

    # Effective saturation at porosity theta_s should be 1.0
    se_sat = engine.compute_effective_saturation(params.theta_s)
    assert se_sat == 1.0

    # Intermediate moisture
    se_mid = engine.compute_effective_saturation((params.theta_r + params.theta_s) / 2.0)
    assert 0.49 <= se_mid <= 0.51


def test_matric_suction_curve_monotonicity() -> None:
    engine = UnsaturatedHydraulicsEngine(SoilTextureClass.LOAM)

    # Drier soil should exert higher matric suction
    suction_dry = engine.matric_suction_from_water_content(0.12)
    suction_wet = engine.matric_suction_from_water_content(0.35)

    assert suction_dry > suction_wet
    assert suction_dry > 50.0  # High suction in dry soil
    assert suction_wet < 15.0  # Low suction near field capacity

    # Reversibility test: theta(h) from suction
    theta_recovered = engine.water_content_from_suction(suction_wet)
    assert abs(theta_recovered - 0.35) < 0.02


def test_unsaturated_hydraulic_conductivity_decay() -> None:
    engine = UnsaturatedHydraulicsEngine(SoilTextureClass.SANDY_LOAM)
    params = engine.params

    # Saturated conductivity matches k_sat
    k_sat = engine.unsaturated_hydraulic_conductivity(params.theta_s)
    assert abs(k_sat - params.k_sat) < 1e-4

    # Dry soil conductivity drops drastically (by orders of magnitude)
    k_dry = engine.unsaturated_hydraulic_conductivity(params.theta_r + 0.05)
    assert k_dry < 0.1 * params.k_sat
    assert k_dry >= 0.0


def test_soil_texture_catalog_properties() -> None:
    # Compare Sand vs Loam vs Basalt Clay
    sandy = SOIL_HYDRAULIC_CATALOG[SoilTextureClass.SANDY_LOAM]
    clay = SOIL_HYDRAULIC_CATALOG[SoilTextureClass.BASALT_CLAY]

    assert isinstance(sandy, VanGenuchtenParams)
    assert sandy.k_sat > clay.k_sat  # Sand infiltrates faster than clay
    assert clay.theta_s > sandy.theta_s  # Clay has higher porosity/retention
    assert sandy.n > clay.n  # Steeper pore size distribution for sand


def test_subsurface_wetted_bulb_simulation() -> None:
    engine = UnsaturatedHydraulicsEngine(SoilTextureClass.LOAM)

    # 1.6 L/h emitter running for 2.0 hours (3.2 L total) at 20cm depth
    bulb = engine.simulate_subsurface_wetted_bulb(
        emitter_depth_cm=20.0,
        emitter_discharge_lph=1.6,
        application_duration_hours=2.0,
        initial_volumetric_moisture=0.18,
    )

    assert bulb.depth_cm == 20.0
    assert 20.0 <= bulb.radial_width_cm <= 60.0
    assert 20.0 <= bulb.vertical_height_cm <= 65.0
    assert bulb.wetted_volume_liters > 0.0
    assert bulb.effective_saturation > 0.0
    assert bulb.matric_suction_kpa > 0.0
    assert bulb.deep_percolation_loss_pct == 0.0  # Stays within root zone (< 60cm bottom)


def test_deep_percolation_on_overirrigation() -> None:
    engine = UnsaturatedHydraulicsEngine(SoilTextureClass.SANDY_LOAM)

    # Excessive 6-hour watering with 3.0 L/h emitter buried at 35cm
    bulb_overwatered = engine.simulate_subsurface_wetted_bulb(
        emitter_depth_cm=35.0,
        emitter_discharge_lph=3.0,
        application_duration_hours=6.0,
        initial_volumetric_moisture=0.32,
    )

    # Bottom exceeds 60cm root zone, triggering deep percolation loss
    assert bulb_overwatered.deep_percolation_loss_pct > 0.0
    assert bulb_overwatered.deep_percolation_loss_pct <= 35.0
