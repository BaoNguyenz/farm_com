"""
Unit tests for Agricultural GHG Carbon Accounting Engine.
Validates Scope 1 (N2O fertilization), Scope 2 (EVN pumping electricity),
soil carbon sequestration credits, and farm-wide emission intensity ratings.
"""

from backend.core.carbon_accounting import (
    CarbonAccountingEngine,
    ZoneCarbonFootprint,
    FarmCarbonReport,
)
from backend.core.twin_state import create_default_farm


def test_carbon_emission_factors_defaults():
    engine = CarbonAccountingEngine()
    assert engine.factors.grid_electricity_kg_co2e_per_kwh == 0.7221
    assert engine.factors.pumping_energy_kwh_per_m3 == 0.35
    assert engine.factors.n_fertilizer_direct_kg_co2e_per_kg_n == 4.164


def test_zone_emissions_calculation():
    farm = create_default_farm(width=2, height=2)
    zone = farm.zones[0]
    zone.ndvi = 0.80

    engine = CarbonAccountingEngine()
    # 1,000 L of water (1 m3) -> 0.35 kWh -> 0.35 * 0.7221 = 0.2527 kg CO2e
    # 0.5 kg N -> 0.5 * 4.164 = 2.082 kg CO2e
    # Sequestration = 25m2 * 0.0068 * 1.0 day * 0.8 = 0.136 kg CO2e
    res = engine.calculate_zone_emissions(
        zone=zone,
        water_liters_used=1000.0,
        nitrogen_applied_kg=0.5,
        elapsed_days=1.0,
        zone_area_m2=25.0
    )

    assert isinstance(res, ZoneCarbonFootprint)
    assert res.zone_id == zone.id
    assert res.electricity_kwh == 0.35
    assert abs(res.electricity_emissions_kg_co2e - 0.2527) < 0.01
    assert abs(res.fertilizer_emissions_kg_co2e - 2.082) < 0.01
    assert abs(res.carbon_sequestration_kg_co2e - 0.136) < 0.01
    assert res.net_carbon_balance_kg_co2e > 0.0


def test_vegetative_sequestration_scaling():
    farm = create_default_farm(width=2, height=2)
    zone_healthy = farm.zones[0]
    zone_healthy.ndvi = 0.90

    zone_degraded = farm.zones[1]
    zone_degraded.ndvi = 0.25

    engine = CarbonAccountingEngine()
    res_healthy = engine.calculate_zone_emissions(zone_healthy, elapsed_days=5.0)
    res_degraded = engine.calculate_zone_emissions(zone_degraded, elapsed_days=5.0)

    # Healthy canopy accrues significantly higher sequestration credits
    assert res_healthy.carbon_sequestration_kg_co2e > res_degraded.carbon_sequestration_kg_co2e


def test_farm_carbon_report_aggregation():
    farm = create_default_farm(width=3, height=3)
    engine = CarbonAccountingEngine()

    report = engine.calculate_farm_emissions(
        farm=farm,
        elapsed_days=2.0,
        total_water_liters=9000.0,
        total_nitrogen_kg=4.5
    )

    assert isinstance(report, FarmCarbonReport)
    assert report.farm_id == farm.farm_id
    assert report.elapsed_days == 2.0
    assert len(report.zone_breakdowns) == 9
    assert report.total_electricity_kwh > 0.0
    assert report.scope1_emissions_kg_co2e > 0.0
    assert report.scope2_emissions_kg_co2e > 0.0
    assert report.total_sequestration_kg_co2e > 0.0
    assert report.carbon_rating in ("A_climate_positive", "B_low_carbon", "C_moderate", "D_high_carbon")


def test_climate_positive_rating():
    farm = create_default_farm(width=2, height=2)
    engine = CarbonAccountingEngine()

    # Zero inputs, pure carbon sink from thriving canopy
    report = engine.calculate_farm_emissions(
        farm=farm,
        elapsed_days=10.0,
        total_water_liters=0.0,
        total_nitrogen_kg=0.0
    )

    assert report.total_gross_emissions_kg_co2e == 0.0
    assert report.total_sequestration_kg_co2e > 0.0
    assert report.net_footprint_kg_co2e < 0.0
    assert report.carbon_rating == "A_climate_positive"
