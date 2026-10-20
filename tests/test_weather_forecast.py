"""
Unit tests for Agro-meteorological Engine, VPD calculations & Frost Hazard
"""
import pytest
from backend.ingestion.weather_forecast import WeatherAnalyticsEngine, HourlyWeatherData


def test_saturation_vapor_pressure():
    # At 20 C, es is roughly 2.34 kPa
    es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(20.0)
    assert 2.30 <= es <= 2.40


def test_vpd_calculation():
    # At 25 C and 50% RH: es ~ 3.167 kPa, ea ~ 1.583 kPa -> VPD ~ 1.58 kPa
    vpd = WeatherAnalyticsEngine.calculate_vpd(temp_c=25.0, rh_pct=50.0)
    assert 1.40 <= vpd <= 1.70


def test_vpd_classification():
    status_sweetspot = WeatherAnalyticsEngine.classify_vpd_range(1.0)
    assert status_sweetspot == "HEALTHY_VEGETATIVE_SWEETSPOT"

    status_humid = WeatherAnalyticsEngine.classify_vpd_range(0.2)
    assert status_humid == "TOO_HUMID_FUNGAL_RISK"


def test_spray_drift_hazard_high_wind():
    # 25 km/h wind -> excessive
    assessment = WeatherAnalyticsEngine.assess_spray_drift_hazard(
        wind_speed_ms=7.0, temp_c=22.0, rh_pct=60.0
    )
    assert assessment["spray_permitted"] is False
    assert assessment["classification"] == "EXCESSIVE_WIND_PROHIBITED"


def test_frost_hazard_subzero():
    alert = WeatherAnalyticsEngine.assess_frost_hazard(
        temp_c=-1.5, dew_point_c=-2.0, wind_speed_ms=0.5
    )
    assert alert is not None
    assert alert.severity == "CRITICAL"
    assert "FROST" in alert.category
