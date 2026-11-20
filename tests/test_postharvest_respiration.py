"""
Unit tests for Post-Harvest Fruit Respiration & Shelf-Life Kinetics.
"""

from backend.core.postharvest_respiration import (
    COMMODITY_CATALOG,
    PerishableCommodity,
    PostHarvestRespirationEngine,
    RespirationKineticsResult,
)


def test_respiration_rate_temperature_suppression_at_cold_store() -> None:
    engine = PostHarvestRespirationEngine(PerishableCommodity.STRAWBERRIES)

    # 2C cold storage vs 25C ambient heat
    res_cold = engine.evaluate_respiration(storage_temp_c=2.0)
    res_warm = engine.evaluate_respiration(storage_temp_c=25.0)

    assert isinstance(res_cold, RespirationKineticsResult)
    # Respiration should be slowed down by ~5x to 8x at cold temperatures
    assert res_cold.r_o2_ml_kg_h < res_warm.r_o2_ml_kg_h * 0.25
    assert res_cold.daily_heat_generation_kj_kg < res_warm.daily_heat_generation_kj_kg


def test_respiratory_quotient_fermentation_spike_under_hypoxia() -> None:
    engine = PostHarvestRespirationEngine(PerishableCommodity.STRAWBERRIES)

    # Aerobic air (20.9% O2) vs extreme hypoxia (0.5% O2)
    res_air = engine.evaluate_respiration(storage_temp_c=2.0, o2_pct=20.9)
    res_hypoxia = engine.evaluate_respiration(storage_temp_c=2.0, o2_pct=0.5)

    assert res_air.anaerobic_fermentation_risk is False
    assert res_air.respiratory_quotient < 1.2

    # Under hypoxia, fermentation kicks in with severe RQ surge (> 2.0)
    assert res_hypoxia.anaerobic_fermentation_risk is True
    assert res_hypoxia.respiratory_quotient > 2.0


def test_commodity_catalog_parameters() -> None:
    strawberry = COMMODITY_CATALOG[PerishableCommodity.STRAWBERRIES]
    tomato = COMMODITY_CATALOG[PerishableCommodity.CHERRY_TOMATOES]

    assert strawberry.optimal_storage_temp_c < tomato.optimal_storage_temp_c
    assert tomato.chilling_injury_temp_c == 8.0  # Cold sensitive
    assert strawberry.v_max_o2_at_20c_ml_kg_h > tomato.v_max_o2_at_20c_ml_kg_h


def test_transpirational_water_loss_under_variable_humidity() -> None:
    engine = PostHarvestRespirationEngine(PerishableCommodity.BUTTERHEAD_LETTUCE)

    # 95% high humidity vs 65% dry air
    res_humid = engine.evaluate_respiration(storage_temp_c=4.0, ambient_rh_pct=95.0)
    res_dry = engine.evaluate_respiration(storage_temp_c=4.0, ambient_rh_pct=65.0)

    # Low humidity drives drastically higher transpiration loss
    assert res_dry.hourly_weight_loss_pct > res_humid.hourly_weight_loss_pct * 4.0


def test_temperature_abuse_shelf_life_depletion() -> None:
    engine = PostHarvestRespirationEngine(PerishableCommodity.STRAWBERRIES)

    # Continuous optimal 1.5C vs 18C temperature abuse for 2 days
    res_opt = engine.evaluate_respiration(storage_temp_c=1.5, elapsed_days_in_store=2.0)
    res_abused = engine.evaluate_respiration(storage_temp_c=18.0, elapsed_days_in_store=2.0)

    assert res_opt.remaining_shelf_life_days > 10.0
    assert res_abused.remaining_shelf_life_days < 3.0
    assert res_opt.freshness_index_score > res_abused.freshness_index_score


def test_chilling_injury_detection() -> None:
    engine_tomato = PostHarvestRespirationEngine(PerishableCommodity.CHERRY_TOMATOES)

    # 4C triggers chilling injury on tomatoes (threshold 8C)
    res_chilled = engine_tomato.evaluate_respiration(storage_temp_c=4.0)
    res_safe = engine_tomato.evaluate_respiration(storage_temp_c=12.0)

    assert res_chilled.chilling_injury_risk is True
    assert res_safe.chilling_injury_risk is False
