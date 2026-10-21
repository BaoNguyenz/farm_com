"""
Unit tests for External Data Ingestion Pipeline (Phase 2):
Open-Meteo Weather Client, Sentinel-2 Satellite Generator, and IoT Sensor Simulator.
"""
import pytest
import asyncio
import time
from backend.ingestion.weather_client import WeatherClient
from backend.ingestion.satellite_client import SatelliteClient
from backend.ingestion.sensor_sim import SensorSimulator
from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherTelemetry


@pytest.fixture
def sample_farm():
    weather = WeatherTelemetry(
        temp_c=24.0, temp_max=28.0, temp_min=16.0,
        humidity_percent=65.0, wind_speed_ms=2.0, solar_radiation_mj=18.0,
        precipitation_mm=0.0, cloud_cover_pct=15.0
    )
    zones = [
        PlotZone(
            id="ZONE_0_0", x=0, y=0, crop_type="maize",
            soil_moisture_pct=60.0, soil_temp_c=22.0,
            ndvi=0.75, ndwi=0.35, health_status="healthy"
        ),
        PlotZone(
            id="ZONE_0_1", x=0, y=1, crop_type="maize",
            soil_moisture_pct=30.0, soil_temp_c=23.0,
            ndvi=0.65, ndwi=0.10, health_status="water_stressed"
        ),
    ]
    return FarmDigitalTwin(farm_name="Test Ingestion Farm", current_weather=weather, zones=zones)


def test_weather_client_cache_and_invalidation():
    client = WeatherClient(cache_ttl_seconds=10)
    assert client.is_cache_valid() is False

    # Simulate cached telemetry
    mock_telemetry = WeatherTelemetry(
        temp_c=25.0, temp_max=29.0, temp_min=17.0,
        humidity_percent=60.0, wind_speed_ms=2.5, solar_radiation_mj=19.0,
        precipitation_mm=0.0, cloud_cover_pct=10.0
    )
    client._cached_telemetry = mock_telemetry
    client._cache_timestamp = time.time()
    assert client.is_cache_valid() is True

    # Invalidate
    client.clear_cache()
    assert client.is_cache_valid() is False


def test_satellite_client_full_spectral_bands():
    client = SatelliteClient()
    bands_healthy = asyncio.run(client.get_full_multispectral_bands("ZONE_0_0"))
    bands_stressed = asyncio.run(client.get_full_multispectral_bands("Z_2_1"))

    # Healthy zone: high NIR, low Red
    assert bands_healthy["nir"] > bands_healthy["red"]
    assert bands_healthy["nir"] >= 0.50

    # Stressed zone: lower NIR, higher Red
    assert bands_stressed["red"] > bands_healthy["red"]
    assert bands_stressed["nir"] < bands_healthy["nir"]


def test_satellite_cloud_masking():
    client = SatelliteClient()
    clear_sky = client.assess_cloud_contamination(cloud_cover_pct=10.0)
    assert clear_sky["cloud_masked"] is False
    assert clear_sky["usable_for_indices"] is True
    assert clear_sky["optical_quality_score"] == 0.90

    heavy_cloud = client.assess_cloud_contamination(cloud_cover_pct=65.0)
    assert heavy_cloud["cloud_masked"] is True
    assert heavy_cloud["usable_for_indices"] is False
    assert heavy_cloud["optical_quality_score"] == 0.35


def test_sensor_simulator_diurnal_drying(sample_farm):
    sim = SensorSimulator(sample_farm)

    # Day drying (08:00)
    sim.simulation_hour = 10.0
    start_moisture = sample_farm.zones[0].soil_moisture_pct
    sim.step_simulation(elapsed_hours=2.0)
    day_loss = start_moisture - sample_farm.zones[0].soil_moisture_pct
    assert day_loss > 0.0

    # Night drying (01:00)
    sim.simulation_hour = 1.0
    night_start = sample_farm.zones[0].soil_moisture_pct
    sim.step_simulation(elapsed_hours=2.0)
    night_loss = night_start - sample_farm.zones[0].soil_moisture_pct
    assert night_loss > 0.0
    # Day drying should generally exceed night drying
    assert day_loss >= night_loss * 0.8


def test_sensor_simulator_irrigation_recharge(sample_farm):
    sim = SensorSimulator(sample_farm)
    stressed_zone = sample_farm.zones[1]
    assert stressed_zone.health_status == "water_stressed"

    # Apply 1000L recharge
    res = sim.apply_irrigation_recharge(zone_id="ZONE_0_1", water_liters=1000.0)
    assert res["zone_id"] == "ZONE_0_1"
    assert res["applied_liters"] == 1000.0
    assert res["current_moisture_pct"] >= 40.0
    assert res["status"] == "healthy"
