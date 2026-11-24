"""
Unit test suite for Solar Thermal Crop Drying Kinetics & Nutrient Retention Engine.
"""

import pytest

from backend.core.solar_drying_kinetics import (
    COMMODITY_CATALOG,
    CropDryingCommodity,
    DryingQualityGrade,
    SolarDryingKineticsEngine,
)


def test_moisture_basis_conversion():
    """Verify wet-to-dry and dry-to-wet moisture basis mathematical conversions."""
    engine = SolarDryingKineticsEngine()

    # 90% wet basis = 0.90 / (1 - 0.90) = 9.0 dry basis (kg water / kg dry matter)
    db = engine.wet_to_dry_basis(90.0)
    assert db == 9.0

    wb = engine.dry_to_wet_basis(9.0)
    assert wb == 90.0

    # 12% wet basis target
    db_12 = engine.wet_to_dry_basis(12.0)
    assert 0.13 <= db_12 <= 0.14
    assert engine.dry_to_wet_basis(db_12) == 12.0

    # Error handling
    with pytest.raises(ValueError, match="cannot be >= 100%"):
        engine.wet_to_dry_basis(100.0)

    with pytest.raises(ValueError, match="cannot be negative"):
        engine.dry_to_wet_basis(-1.0)


def test_equilibrium_moisture_isotherm():
    """Verify equilibrium moisture content (EMC) increases with ambient air relative humidity."""
    engine = SolarDryingKineticsEngine()
    props = COMMODITY_CATALOG[CropDryingCommodity.STRAWBERRY_SLICES]

    emc_dry = engine.calculate_equilibrium_moisture(temp_c=50.0, rh_pct=15.0, props=props)
    emc_humid = engine.calculate_equilibrium_moisture(temp_c=50.0, rh_pct=60.0, props=props)

    assert emc_dry > 0.02
    assert emc_humid > emc_dry


def test_effective_diffusivity_arrhenius():
    """Verify Fickian moisture diffusivity D_eff increases with temperature according to Arrhenius law."""
    engine = SolarDryingKineticsEngine()
    props = COMMODITY_CATALOG[CropDryingCommodity.STRAWBERRY_SLICES]

    d_eff_40 = engine.calculate_effective_diffusivity(40.0, props)
    d_eff_55 = engine.calculate_effective_diffusivity(55.0, props)

    assert 1e-10 <= d_eff_40 <= 1e-8
    assert d_eff_55 > d_eff_40  # Higher thermal kinetic energy accelerates internal moisture migration


def test_water_activity_threshold():
    """Verify water activity drops below safe microbiological storage threshold (0.60)."""
    engine = SolarDryingKineticsEngine()

    # Fresh fruit (90% wet basis) has high water activity > 0.90
    aw_fresh = engine.calculate_water_activity(90.0, target_wb_pct=12.0)
    assert aw_fresh >= 0.90

    # Dried fruit at target 12% moisture has aw <= 0.60
    aw_target = engine.calculate_water_activity(12.0, target_wb_pct=12.0)
    assert aw_target <= 0.60


def test_strawberry_drying_trajectory():
    """Verify drying strawberry slices over time follows monotonic moisture decay."""
    engine = SolarDryingKineticsEngine()

    state_0h = engine.simulate_drying_step(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        elapsed_hours=0.0,
        chamber_air_temp_c=48.0,
        chamber_air_rh_pct=20.0,
    )
    assert state_0h.moisture_ratio_mr == 1.0
    assert state_0h.is_drying_completed is False

    state_8h = engine.simulate_drying_step(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        elapsed_hours=8.0,
        chamber_air_temp_c=48.0,
        chamber_air_rh_pct=20.0,
    )
    assert state_8h.moisture_ratio_mr < state_0h.moisture_ratio_mr
    assert state_8h.moisture_wet_basis_pct < state_0h.moisture_wet_basis_pct

    # After 24 hours at 48°C and 20% RH, drying completes with Grade AAA quality
    state_24h = engine.simulate_drying_step(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        elapsed_hours=24.0,
        chamber_air_temp_c=48.0,
        chamber_air_rh_pct=20.0,
    )
    assert state_24h.is_drying_completed is True
    assert state_24h.water_activity_aw <= 0.60
    assert state_24h.vitamin_c_retention_pct >= 70.0
    assert state_24h.quality_grade == DryingQualityGrade.GRADE_AAA_PREMIUM


def test_thermal_abuse_quality_downgrade():
    """Verify excessive drying temperature (>52°C for strawberries) causes thermal abuse and downgrade."""
    engine = SolarDryingKineticsEngine()

    # Heated at 68°C (violates max safe temperature 52°C)
    state_overheated = engine.simulate_drying_step(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        elapsed_hours=18.0,
        chamber_air_temp_c=68.0,
        chamber_air_rh_pct=15.0,
    )

    assert state_overheated.chamber_air_temp_c > 52.0
    # Overheating causes degradation and non-AAA quality grade
    assert state_overheated.quality_grade != DryingQualityGrade.GRADE_AAA_PREMIUM


def test_commodity_catalog_coverage():
    """Verify all 5 standard crops are calibrated in commodity catalog."""
    expected = [
        CropDryingCommodity.STRAWBERRY_SLICES,
        CropDryingCommodity.CHERRY_TOMATOES,
        CropDryingCommodity.ARTICHOKE_HERBAL_TEA,
        CropDryingCommodity.SHIITAKE_MUSHROOMS,
        CropDryingCommodity.ARABICA_COFFEE_BEANS,
    ]
    for crop in expected:
        assert crop in COMMODITY_CATALOG
        props = COMMODITY_CATALOG[crop]
        assert props.initial_moisture_wb_pct > props.target_moisture_wb_pct
        assert props.activation_energy_kj_mol > 20.0
