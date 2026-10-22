"""
Unit tests for Digital Twin Tick Simulation Engine (Task 3.2)
"""
import pytest
from backend.core.twin_state import create_default_farm
from backend.core.tick_engine import DigitalTwinTickEngine


@pytest.fixture
def farm_env():
    return create_default_farm(width=3, height=3)


def test_single_hour_tick_advancement(farm_env):
    engine = DigitalTwinTickEngine()
    initial_gdd = farm_env.zones[0].accumulated_gdd
    initial_moisture = farm_env.zones[0].soil_moisture_pct

    result = engine.advance_tick(farm=farm_env, elapsed_hours=1.0, rain_mm=0.0)

    assert result["elapsed_hours"] == 1.0
    assert result["hourly_et0_mm"] > 0.0
    assert result["hourly_gdd"] > 0.0
    # GDD should increase
    assert farm_env.zones[0].accumulated_gdd > initial_gdd
    # Moisture should decrease without rain
    assert farm_env.zones[0].soil_moisture_pct < initial_moisture


def test_rainfall_recharges_soil_during_tick(farm_env):
    engine = DigitalTwinTickEngine()
    initial_moisture = farm_env.zones[0].soil_moisture_pct

    # Heavy rain event of 15mm
    result = engine.advance_tick(farm=farm_env, elapsed_hours=1.0, rain_mm=15.0)

    assert result["rain_mm"] == 15.0
    # Soil moisture should increase with heavy rain
    assert farm_env.zones[0].soil_moisture_pct > initial_moisture


def test_gravity_drainage_on_saturated_soil(farm_env):
    engine = DigitalTwinTickEngine()
    zone = farm_env.zones[0]
    zone.soil_moisture_pct = 92.0  # Saturated above 80%

    result = engine.advance_tick(farm=farm_env, elapsed_hours=2.0, rain_mm=0.0)

    # Moisture should drop significantly due to drainage + evapotranspiration
    assert zone.soil_moisture_pct < 92.0


def test_stage_transition_with_gdd_accumulation(farm_env):
    engine = DigitalTwinTickEngine()
    zone = farm_env.zones[0]
    zone.growth_stage = "seedling"
    zone.accumulated_gdd = 95.0

    # Advance enough time with warm weather to cross 100 GDD
    result = engine.advance_tick(farm=farm_env, elapsed_hours=10.0, rain_mm=0.0)

    assert zone.accumulated_gdd >= 100.0
    assert zone.growth_stage == "vegetative"
    assert any(t["zone_id"] == zone.id for t in result["stage_transitions"])


def test_24_hour_multi_tick_simulation_cycle(farm_env):
    engine = DigitalTwinTickEngine()

    # Simulate 24 hourly ticks (one full diurnal day)
    for _ in range(24):
        engine.advance_tick(farm=farm_env, elapsed_hours=1.0, rain_mm=0.0)

    summary = farm_env.get_spatial_summary()
    assert summary["total_zones"] == 9
    assert farm_env.last_sync_timestamp > 0.0
