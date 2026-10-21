"""
Unit tests for Agro-meteorological Engine, VPD calculations & Frost Hazard
"""
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


def test_actual_vapor_pressure_at_100_percent_humidity():
    # At 100% RH, ea == es
    es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(24.0)
    ea = WeatherAnalyticsEngine.calculate_actual_vapor_pressure(temp_c=24.0, rh_pct=100.0)
    assert abs(es - ea) < 1e-4

    # At 0% RH, ea == 0
    ea_dry = WeatherAnalyticsEngine.calculate_actual_vapor_pressure(temp_c=24.0, rh_pct=0.0)
    assert ea_dry == 0.0


def test_extraterrestrial_radiation_seasonal_variation():
    # Northern hemisphere at 21 degrees latitude (Northern Vietnam)
    # Summer solstice day ~172 vs Winter solstice day ~355
    ra_summer = WeatherAnalyticsEngine.estimate_extraterrestrial_radiation(
        latitude_deg=21.0, day_of_year=172
    )
    ra_winter = WeatherAnalyticsEngine.estimate_extraterrestrial_radiation(
        latitude_deg=21.0, day_of_year=355
    )
    assert ra_summer > ra_winter
    assert ra_summer >= 35.0
    assert ra_winter >= 20.0


def test_solar_radiation_hargreaves_inland_vs_coastal():
    # Delta T = 12C, Ra = 30 MJ/m2
    rs_inland = WeatherAnalyticsEngine.estimate_solar_radiation_hargreaves(
        t_max=32.0, t_min=20.0, ra_mj=30.0, coastal=False
    )
    rs_coastal = WeatherAnalyticsEngine.estimate_solar_radiation_hargreaves(
        t_max=32.0, t_min=20.0, ra_mj=30.0, coastal=True
    )
    # Coastal has higher kr factor (0.19 vs 0.16)
    assert rs_coastal > rs_inland
    assert 14.0 <= rs_inland <= 18.0
    assert 17.0 <= rs_coastal <= 22.0


def test_spray_drift_ideal_window():
    # 2.5 m/s = 9 km/h, 24C, 65% RH
    assessment = WeatherAnalyticsEngine.assess_spray_drift_hazard(
        wind_speed_ms=2.5, temp_c=24.0, rh_pct=65.0
    )
    assert assessment["spray_permitted"] is True
    assert assessment["classification"] == "IDEAL_SPRAY_WINDOW"


def test_spray_drift_temperature_inversion_calm_air():
    # 0.5 m/s = 1.8 km/h (< 3 km/h inversion risk)
    assessment = WeatherAnalyticsEngine.assess_spray_drift_hazard(
        wind_speed_ms=0.5, temp_c=18.0, rh_pct=70.0
    )
    assert assessment["spray_permitted"] is False
    assert assessment["classification"] == "DANGEROUS_TEMPERATURE_INVERSION"


def test_spray_drift_rapid_droplet_evaporation():
    # 3.0 m/s = 10.8 km/h, but hot (33C) and dry (30% RH)
    assessment = WeatherAnalyticsEngine.assess_spray_drift_hazard(
        wind_speed_ms=3.0, temp_c=33.0, rh_pct=30.0
    )
    assert assessment["spray_permitted"] is False
    assert assessment["classification"] == "RAPID_DROPLET_EVAPORATION"


def test_advective_wind_freeze_alert():
    # Subzero with 3.5 m/s active wind -> Advective freeze
    alert = WeatherAnalyticsEngine.assess_frost_hazard(
        temp_c=-2.0, dew_point_c=-3.0, wind_speed_ms=3.5
    )
    assert alert is not None
    assert alert.severity == "HIGH"
    assert "FREEZE" in alert.category
    assert "Active Wind Chill" in alert.headline


def test_ground_radiation_frost_warning():
    # Cold ground inversion: 1.5 C air temp, negative dew point
    alert = WeatherAnalyticsEngine.assess_frost_hazard(
        temp_c=1.5, dew_point_c=-1.0, wind_speed_ms=1.0
    )
    assert alert is not None
    assert alert.severity == "WARNING"
    assert "Inversion" in alert.headline


def test_aggregate_daily_metrics_24h_cycle():
    # Build 24 hours of sample weather
    hourly = []
    for h in range(24):
        hourly.append(
            HourlyWeatherData(
                timestamp=f"2026-10-20T{h:02d}:00:00",
                temperature_c=18.0 + 8.0 * (1.0 if 10 <= h <= 16 else 0.0),
                relative_humidity_pct=80.0 - 25.0 * (1.0 if 10 <= h <= 16 else 0.0),
                wind_speed_ms=2.0,
                solar_radiation_wm2=450.0 if 8 <= h <= 17 else 0.0,
                precipitation_mm=2.5 if h == 14 else 0.0,
            )
        )

    daily = WeatherAnalyticsEngine.aggregate_daily_metrics(
        hourly_records=hourly, latitude=11.94, day_of_year=293
    )
    assert daily["t_max_c"] == 26.0
    assert daily["t_min_c"] == 18.0
    assert daily["total_precipitation_mm"] == 2.5
    assert daily["vpd_mean_kpa"] > 0.0
    assert daily["solar_radiation_rs_mj"] > 0.0
