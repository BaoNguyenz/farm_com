"""
Unit tests for Agrivoltaic Microgrid & Battery Energy Storage (BESS) Engine.
"""

import pytest

from backend.core.microgrid import (
    BatteryStorageSystem,
    MicrogridController,
    MicrogridMode,
    SolarPVArray,
    TariffTier,
)


def test_solar_pv_zero_and_peak_generation():
    solar = SolarPVArray(installed_capacity_kwp=20.0, panel_area_m2=100.0)

    # Night / zero irradiance
    assert solar.calculate_power(irradiance_w_m2=0.0, ambient_temp_c=22.0) == 0.0
    assert solar.calculate_power(irradiance_w_m2=-10.0, ambient_temp_c=22.0) == 0.0

    # Strong midday sun (1000 W/m2 at 25C)
    # Cell temp = 25 + 25*(1) = 50C -> delta = 25C -> derate = 1 - 0.0038*25 = 0.905
    # Power = 100 * 1000 * 0.205 * 0.905 / 1000 = 18.55 kW
    power = solar.calculate_power(irradiance_w_m2=1000.0, ambient_temp_c=25.0)
    assert 17.0 <= power <= 20.0


def test_battery_storage_charge_and_efficiency():
    bess = BatteryStorageSystem(
        capacity_kwh=50.0,
        max_charge_power_kw=10.0,
        current_soc=0.20,
        min_soc=0.15,
        max_soc=0.95,
        roundtrip_efficiency=0.90,
    )

    # Attempt to charge with 15 kW for 1 hr (capped at max 10 kW)
    stored_kwh, curtailed = bess.charge(power_kw=15.0, duration_hours=1.0)
    # 10 kW * 1h * 0.90 = 9.0 kWh stored
    assert stored_kwh == pytest.approx(9.0, 0.01)
    assert curtailed == pytest.approx(5.0, 0.01)
    # New SoC: 0.20 + (9.0 / 50.0) = 0.38
    assert bess.current_soc == pytest.approx(0.38, 0.01)


def test_battery_storage_discharge_limits():
    bess = BatteryStorageSystem(
        capacity_kwh=40.0,
        max_discharge_power_kw=10.0,
        current_soc=0.25,
        min_soc=0.15,
        roundtrip_efficiency=0.90,
    )
    # Usable energy to min_soc (0.10 * 40 = 4 kWh cell energy)
    # With 0.90 roundtrip efficiency, deliverable = 4 * 0.90 = 3.6 kWh
    delivered, deficit = bess.discharge(power_kw=10.0, duration_hours=1.0)
    assert delivered == pytest.approx(3.6, 0.01)
    assert deficit == pytest.approx(6.4, 0.01)
    assert bess.current_soc == pytest.approx(0.15, 0.01)


def test_tariff_tier_schedule():
    # 02:00 -> Off-peak
    assert MicrogridController.get_tariff_tier(2) == TariffTier.OFF_PEAK
    # 10:00 -> Peak
    assert MicrogridController.get_tariff_tier(10) == TariffTier.PEAK
    # 14:00 -> Normal
    assert MicrogridController.get_tariff_tier(14) == TariffTier.NORMAL
    # 18:00 -> Peak
    assert MicrogridController.get_tariff_tier(18) == TariffTier.PEAK


def test_microgrid_solar_self_consumption_surplus_to_battery():
    solar = SolarPVArray(installed_capacity_kwp=30.0, panel_area_m2=150.0)
    battery = BatteryStorageSystem(capacity_kwh=50.0, current_soc=0.50)
    controller = MicrogridController(solar=solar, battery=battery)

    # Midday: 800 W/m2 generates ~20+ kW solar, load is only 5.0 kW
    result = controller.dispatch(
        load_kw=5.0,
        irradiance_w_m2=800.0,
        ambient_temp_c=28.0,
        hour_of_day=12,
        grid_available=True,
    )

    assert result.solar_power_generated_kw > 15.0
    assert result.solar_used_directly_kw == 5.0
    assert result.solar_to_battery_kw > 0.0
    assert result.grid_imported_kw == 0.0
    assert result.battery_soc_after > 0.50
    assert result.carbon_avoided_kg_co2e > 0.0


def test_microgrid_peak_shaving_discharge():
    solar = SolarPVArray(installed_capacity_kwp=10.0, panel_area_m2=50.0)
    battery = BatteryStorageSystem(capacity_kwh=40.0, current_soc=0.80)
    controller = MicrogridController(solar=solar, battery=battery)

    # Peak hour (18:00 sunset, 0 irradiance), irrigation load 8.0 kW
    result = controller.dispatch(
        load_kw=8.0,
        irradiance_w_m2=0.0,
        ambient_temp_c=27.0,
        hour_of_day=18,
        grid_available=True,
    )

    assert result.mode == MicrogridMode.PEAK_SHAVING
    assert result.tariff_tier == TariffTier.PEAK
    assert result.solar_power_generated_kw == 0.0
    # Battery discharges 8.0 kW to save peak grid tariff (3076 VND/kWh)
    assert result.battery_discharged_kw == pytest.approx(8.0, 0.01)
    assert result.grid_imported_kw == 0.0
    assert result.solar_savings_vnd == pytest.approx(8.0 * 3076.0, 1.0)


def test_microgrid_islanded_emergency():
    solar = SolarPVArray(installed_capacity_kwp=25.0, panel_area_m2=120.0)
    battery = BatteryStorageSystem(capacity_kwh=40.0, current_soc=0.60)
    controller = MicrogridController(solar=solar, battery=battery)

    # Grid blackout occurs at 14:00, load 12.0 kW, irradiance 500 W/m2
    result = controller.dispatch(
        load_kw=12.0,
        irradiance_w_m2=500.0,
        ambient_temp_c=30.0,
        hour_of_day=14,
        grid_available=False,
    )

    assert result.mode == MicrogridMode.ISLANDED_EMERGENCY
    assert result.grid_imported_kw == 0.0
    # Total supplied should cover load from solar + battery
    total_supplied = result.solar_used_directly_kw + result.battery_discharged_kw
    assert total_supplied == pytest.approx(12.0, 0.1)
