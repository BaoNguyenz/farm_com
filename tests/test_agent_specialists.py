"""
Unit tests for Specialist Agents (Task 4.2, 4.3, 4.4)
Validates Agronomist fungal risk modeling, Irrigation dynamic Kc & root depletion,
and Market EVN TOU electricity tariff & pumping energy economics.
"""
import asyncio
import pytest
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.core.twin_state import create_default_farm


@pytest.fixture
def farm():
    return create_default_farm(width=3, height=3)


def test_agronomist_fungal_risk_modeling(farm):
    agronomist = AgronomistAgent()

    # Configure microclimate: 88% humidity + 21°C is prime fungal sporulation environment
    farm.current_weather.humidity_percent = 88.0
    farm.current_weather.temp_c = 21.0
    farm.get_zone("Z_0_0").soil_moisture_pct = 85.0
    farm.get_zone("Z_0_1").soil_moisture_pct = 85.0

    op = asyncio.run(agronomist.evaluate(farm))


    assert op.urgency == "critical"
    assert "fungal_hazard_zones" in op.data_points
    assert len(op.data_points["fungal_hazard_zones"]) > 0
    assert "bio-fungicide" in op.recommendation.lower() or "fungicide" in op.recommendation.lower()


def test_agronomist_optimal_conditions(farm):
    agronomist = AgronomistAgent()

    # Dry mild weather: low fungal risk
    farm.current_weather.humidity_percent = 55.0
    farm.current_weather.temp_c = 22.0

    # Ensure zones have good moisture and health
    for z in farm.zones:
        z.soil_moisture_pct = 68.0
        z.health_status = "healthy"

    op = asyncio.run(agronomist.evaluate(farm))
    assert op.urgency in ("low", "medium")
    assert len(op.data_points.get("fungal_hazard_zones", [])) == 0


def test_irrigation_dynamic_kc_phenology():
    irrigation = IrrigationAgent()

    # Strawberry phenological Kc progression
    assert irrigation._get_dynamic_kc("Strawberries", "flowering") == 1.15
    assert irrigation._get_dynamic_kc("Strawberries", "fruiting") == 1.10
    assert irrigation._get_dynamic_kc("Strawberries", "vegetative") == 0.75
    assert irrigation._get_dynamic_kc("Strawberries", "harvest_ready") == 0.50
    assert irrigation._get_dynamic_kc("Strawberries", "seedling") == 0.40

    # Non-strawberry crops
    assert irrigation._get_dynamic_kc("Arabica Coffee", "flowering") == 1.05
    assert irrigation._get_dynamic_kc("Arabica Coffee", "fruiting") == 0.95
    assert irrigation._get_dynamic_kc("Arabica Coffee", "vegetative") == 0.70


def test_irrigation_volumetric_demand_and_emergency_wilting(farm):
    irrigation = IrrigationAgent()

    # Severe drought stress on target zone
    target = farm.get_zone("Z_0_0")
    target.soil_moisture_pct = 25.0  # < 35% triggers emergency wilting

    op = asyncio.run(irrigation.evaluate(farm))

    assert op.urgency == "critical"
    assert op.data_points["emergency_wilting"] is True
    assert op.data_points["total_water_liters"] > 0

    # Check volumetric conversion: 1mm depth over 25m2 plot = 25 Liters
    z_match = next(z for z in op.data_points["zones"] if z["zone_id"] == "Z_0_0")
    assert z_match["emergency"] is True
    assert z_match["volume_liters"] == round(z_match["needed_mm"] * 25.0, 1)


def test_market_evn_tou_electricity_schedule():
    market = MarketAgent()

    # Off-peak: 02:00
    offpeak = market.get_electricity_tariff(hour=2.0)
    assert offpeak["tier"] == "off_peak"
    assert offpeak["rate_vnd_kwh"] == 1133.0
    assert offpeak["is_off_peak"] is True
    assert offpeak["is_peak"] is False
    assert offpeak["savings_vs_peak_pct"] > 60.0

    # Peak: 10:00 (09:30 - 11:30)
    peak_morning = market.get_electricity_tariff(hour=10.0)
    assert peak_morning["tier"] == "peak"
    assert peak_morning["rate_vnd_kwh"] == 3076.0
    assert peak_morning["is_peak"] is True

    # Normal: 14:00 (11:30 - 17:00)
    normal_afternoon = market.get_electricity_tariff(hour=14.0)
    assert normal_afternoon["tier"] == "normal"
    assert normal_afternoon["rate_vnd_kwh"] == 1685.0
    assert normal_afternoon["is_peak"] is False


def test_market_pumping_cost_estimation():
    market = MarketAgent()

    # 10,000 Liters pumped
    estimate_normal = market.estimate_pumping_cost(water_volume_liters=10000.0, tier="normal")
    assert estimate_normal["energy_kwh"] == 2.33
    assert estimate_normal["cost_vnd"] == round(2.33 * 1685.0, 0)
    assert estimate_normal["potential_savings_vs_peak_vnd"] > 0

    estimate_peak = market.estimate_pumping_cost(water_volume_liters=10000.0, tier="peak")
    assert estimate_peak["cost_vnd"] == round(2.33 * 3076.0, 0)
    assert estimate_peak["potential_savings_vs_peak_vnd"] == 0.0


def test_market_harvest_valuation(farm):
    market = MarketAgent()

    # Mark zone as harvest ready with high thermal GDD
    harvest_zone = farm.get_zone("Z_1_1")
    harvest_zone.crop_type = "Strawberries"
    harvest_zone.growth_stage = "harvest_ready"
    harvest_zone.accumulated_gdd = 350.0

    op = asyncio.run(market.evaluate(farm))

    assert "harvest_candidates" in op.data_points
    assert len(op.data_points["harvest_candidates"]) >= 1
    assert op.data_points["projected_harvest_value_vnd"] > 0
    candidate = next(c for c in op.data_points["harvest_candidates"] if c["zone_id"] == "Z_1_1")
    assert candidate["crop"] == "Strawberries"
    assert candidate["spot_price_vnd"] == 180000
