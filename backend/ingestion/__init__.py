"""
Data Ingestion Clients and Telemetry Adapters
"""
from backend.ingestion.weather_client import WeatherClient
from backend.ingestion.satellite_client import SatelliteClient
from backend.ingestion.sensor_sim import SensorSimulator
from backend.ingestion.weather_forecast import (
    WeatherAnalyticsEngine,
    HourlyWeatherData,
    MicroclimateRiskAlert,
)

__all__ = [
    "WeatherClient",
    "SatelliteClient",
    "SensorSimulator",
    "WeatherAnalyticsEngine",
    "HourlyWeatherData",
    "MicroclimateRiskAlert",
]
