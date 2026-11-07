"""
Unit tests for Crop Yield Forecasting, Monte Carlo Simulation & Harvest Logistics Engine.
"""

from backend.core.twin_state import create_default_farm
from backend.core.yield_prediction import YieldPredictionEngine


def test_crop_benchmark_resolution():
    engine = YieldPredictionEngine()
    strawberries = engine.get_benchmark("Strawberries")
    assert strawberries.base_temp_c == 10.0
    assert strawberries.target_maturity_gdd == 550.0

    peppers = engine.get_benchmark("Bell Peppers")
    assert peppers.base_temp_c == 12.0
    assert peppers.target_maturity_gdd == 800.0

    unknown = engine.get_benchmark("Exotic Durian")
    assert unknown.crop_name == "Generic Crop"


def test_forecast_zone_biophysical_and_monte_carlo():
    engine = YieldPredictionEngine()
    farm = create_default_farm()
    zone = farm.zones[0]
    zone.crop_type = "Strawberries"
    zone.accumulated_gdd = 440.0
    zone.soil_moisture_pct = 65.0
    zone.health_status = "optimal"

    forecast = engine.forecast_zone(zone, avg_daily_temp_c=22.0, zone_area_m2=25.0)

    # 440 / 550 = 80.0%
    assert forecast.maturity_percentage == 80.0
    assert forecast.estimated_days_to_harvest > 0
    assert forecast.expected_yield_kg > 0.0
    assert forecast.expected_yield_t_ha > 0.0

    # Monte Carlo confidence intervals: p10 <= p50 <= p90
    mc = forecast.monte_carlo_metrics
    assert mc.p10_pessimistic_t_ha <= mc.p50_median_t_ha
    assert mc.p50_median_t_ha <= mc.p90_optimistic_t_ha
    assert mc.yield_risk_coefficient_pct > 0.0


def test_forecast_zone_water_stress_penalty():
    engine = YieldPredictionEngine()
    farm = create_default_farm()

    # Optimal moisture zone
    optimal_zone = farm.zones[0]
    optimal_zone.soil_moisture_pct = 65.0
    optimal_zone.ndwi = 0.35
    fc_optimal = engine.forecast_zone(optimal_zone, zone_area_m2=25.0)

    # Severely water-stressed zone
    stressed_zone = farm.zones[1]
    stressed_zone.crop_type = optimal_zone.crop_type
    stressed_zone.accumulated_gdd = optimal_zone.accumulated_gdd
    stressed_zone.soil_moisture_pct = 20.0
    stressed_zone.ndwi = 0.05
    fc_stressed = engine.forecast_zone(stressed_zone, zone_area_m2=25.0)

    assert fc_stressed.water_stress_penalty_pct > fc_optimal.water_stress_penalty_pct
    assert fc_stressed.expected_yield_kg < fc_optimal.expected_yield_kg


def test_forecast_farm_and_logistics_planning():
    engine = YieldPredictionEngine()
    farm = create_default_farm()

    report = engine.forecast_farm(farm, zone_area_m2=25.0)

    assert report.farm_id == farm.farm_id
    assert report.total_farm_expected_yield_tons > 0.0
    assert 0.0 <= report.average_maturity_pct <= 100.0
    assert len(report.zone_forecasts) == len(farm.zones)

    # Logistics verification
    plan = report.logistics_plan
    assert plan.total_expected_yield_kg > 0.0
    assert plan.total_crates_needed > 0
    assert plan.labor_worker_shifts_needed > 0
    assert plan.cold_storage_volume_m3 > 0.0
    assert plan.post_harvest_precooling_load_kwh > 0.0
    assert plan.earliest_harvest_date <= plan.latest_harvest_date
