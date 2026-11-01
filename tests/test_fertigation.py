"""
Unit tests for Precision Fertigation and Nutrient Dosing Optimizer.
Tests crop nutrition profiles, dosing calculations for Tank A and B,
pH acid neutralization, leaching fraction, and whole-farm batch optimization.
"""

from backend.core.fertigation import (
    FertigationOptimizer,
    FertigationRecipe,
    CropFertigationTarget,
)
from backend.core.twin_state import create_default_farm


def test_crop_fertigation_profiles():
    target_straw = FertigationOptimizer.get_crop_target("Strawberries", "flowering")
    assert isinstance(target_straw, CropFertigationTarget)
    assert target_straw.target_ec_ms_cm == 1.8
    assert target_straw.target_ph_min == 5.8
    assert target_straw.target_ph_max == 6.2

    target_pepper = FertigationOptimizer.get_crop_target("Bell Pepper", "fruiting")
    assert target_pepper.target_ec_ms_cm == 2.4

    # Unknown crop falls back to safe default
    target_unknown = FertigationOptimizer.get_crop_target("Papaya", "seedling")
    assert target_unknown.target_ec_ms_cm == 1.6


def test_fertigation_recipe_calculation():
    farm = create_default_farm(width=2, height=2)
    straw_zone = next(z for z in farm.zones if z.crop_type == "Strawberries")
    straw_zone.growth_stage = "flowering"

    recipe = FertigationOptimizer.compute_recipe(
        straw_zone,
        raw_water_ec_ms_cm=0.30,
        raw_water_ph=7.5
    )

    assert isinstance(recipe, FertigationRecipe)
    assert recipe.zone_id == straw_zone.id
    assert recipe.crop_type == "Strawberries"
    assert recipe.target_ec_ms_cm == 1.8
    assert recipe.ec_deficit_ms_cm == 1.5  # 1.8 - 0.3
    assert recipe.tank_a_injection_ml_m3 > 0.0
    assert recipe.tank_b_injection_ml_m3 > 0.0
    assert recipe.acid_injection_ml_m3 > 0.0  # Acid needed to lower pH 7.5 to 6.0
    assert 10.0 <= recipe.leaching_fraction_pct <= 35.0


def test_acid_buffering_logic():
    farm = create_default_farm(width=2, height=2)
    zone = farm.zones[0]

    # Alkaline water requires acid
    recipe_alkaline = FertigationOptimizer.compute_recipe(zone, raw_water_ph=7.8)
    assert recipe_alkaline.acid_injection_ml_m3 > 0.0
    assert any("buffer alkaline" in rec for rec in recipe_alkaline.recommendations)

    # Already neutral/acidic water does not require acid injection
    recipe_optimal = FertigationOptimizer.compute_recipe(zone, raw_water_ph=6.0)
    assert recipe_optimal.acid_injection_ml_m3 == 0.0


def test_batch_farm_optimization():
    farm = create_default_farm(width=3, height=3)
    recipes = FertigationOptimizer.batch_optimize_farm(farm)

    assert len(recipes) == 9
    for r in recipes:
        assert r.target_ec_ms_cm > 1.0
        assert r.tank_a_injection_ml_m3 > 0.0
        assert r.tank_b_injection_ml_m3 > 0.0
