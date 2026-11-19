"""
Unit test suite for agrivoltaic dual-axis sun-tracking kinetics and astronomical solar position.
"""
import pytest

from backend.core.agrivoltaic_tracking import (
    AgrivoltaicTrackerConfig,
    AgrivoltaicTrackingEngine,
    TrackerMode,
)


def test_solar_position_solar_noon():
    """Verify maximum solar elevation and minimum zenith angle around solar noon."""
    # Day 80 (Spring Equinox) in Dalat (Lat 11.94 N)
    pos_noon = AgrivoltaicTrackingEngine.calculate_solar_position(
        day_of_year=80,
        local_hour=11.8,  # Close to LST 12:00 with Dalat longitude
        latitude_deg=11.94,
        longitude_deg=108.45,
    )

    assert pos_noon.is_sun_up is True
    # At equinox on Lat 11.94, noon elevation is ~ 90 - 11.94 = ~78 degrees
    assert 70.0 < pos_noon.elevation_deg <= 90.0
    assert pos_noon.zenith_deg < 25.0
    assert pytest.approx(pos_noon.elevation_deg + pos_noon.zenith_deg, abs=0.1) == 90.0


def test_solar_declination_seasonal_bounds():
    """Verify seasonal bounds of solar declination."""
    # Summer Solstice (Day 172): ~ +23.45 deg
    pos_summer = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=172, local_hour=12.0)
    assert pytest.approx(pos_summer.declination_deg, abs=0.5) == 23.45

    # Winter Solstice (Day 355): ~ -23.45 deg
    pos_winter = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=355, local_hour=12.0)
    assert pytest.approx(pos_winter.declination_deg, abs=0.5) == -23.45


def test_nighttime_solar_position_and_zero_power():
    """Verify zero power generation when the sun is below horizon."""
    config = AgrivoltaicTrackerConfig()
    pos_night = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=100, local_hour=23.0)

    assert pos_night.is_sun_up is False
    assert pos_night.elevation_deg < 0.0

    state = AgrivoltaicTrackingEngine.calculate_tracking_orientation(
        solar_pos=pos_night,
        config=config,
        ghi_w_m2=0.0,
    )

    assert state.generated_power_kw == 0.0
    assert state.effective_irradiance_w_m2 == 0.0
    assert state.panel_tilt_deg == 0.0


def test_backtracking_low_sun_elevation():
    """Verify backtracking algorithm prevents inter-row shadow projection when sun is low."""
    config = AgrivoltaicTrackerConfig(
        panel_width_meters=2.2,
        row_pitch_meters=6.0,
        max_tilt_deg=55.0,
    )

    # 07:00 morning sun (low elevation ~15-20 deg)
    pos_morning = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=100, local_hour=7.0)

    state_max_power = AgrivoltaicTrackingEngine.calculate_tracking_orientation(
        solar_pos=pos_morning,
        config=config,
        mode=TrackerMode.ASTRONOMICAL_MAX_POWER,
        ghi_w_m2=350.0,
    )

    # With low elevation (<35°), backtracking should engage to flatten tilt
    assert abs(state_max_power.panel_tilt_deg) <= config.max_tilt_deg
    assert state_max_power.is_backtracking_engaged is True


def test_defensive_stow_wind_and_flat_mode():
    """Verify defensive zero-tilt stow mode for windstorm safety."""
    config = AgrivoltaicTrackerConfig()
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=150, local_hour=14.0)

    state_stow = AgrivoltaicTrackingEngine.calculate_tracking_orientation(
        solar_pos=pos,
        config=config,
        mode=TrackerMode.DEFENSIVE_STOW_WIND,
        ghi_w_m2=800.0,
    )

    assert state_stow.mode == TrackerMode.DEFENSIVE_STOW_WIND
    assert state_stow.panel_tilt_deg == 0.0
    assert state_stow.is_backtracking_engaged is False


def test_diurnal_tracking_power_profile():
    """Verify daytime power curve follows diurnal irradiance."""
    config = AgrivoltaicTrackerConfig(installed_capacity_kwp=30.0)
    day_profile = AgrivoltaicTrackingEngine.simulate_day_tracking(
        day_of_year=120,
        config=config,
        peak_ghi_w_m2=900.0,
        ambient_temp_c=26.0,
    )

    assert len(day_profile) == 13  # 06:00 to 18:00 inclusive
    powers = [s.generated_power_kw for s in day_profile]

    # Midday power (index 6, ~12:00) should be highest
    midday_power = powers[6]
    morning_power = powers[0]
    evening_power = powers[-1]

    assert midday_power > morning_power
    assert midday_power > evening_power
    assert midday_power > 15.0  # Significant power generation at solar noon
    assert max(powers) <= config.installed_capacity_kwp
