"""
Unit test suite for Solar Brackish Water Reverse Osmosis Desalination (Phase 18).
"""
import pytest

from backend.core.solar_desalination import SolarDesalinationEngine


@pytest.fixture
def desalination_engine() -> SolarDesalinationEngine:
    return SolarDesalinationEngine()


def test_osmotic_pressure_calculation(desalination_engine: SolarDesalinationEngine) -> None:
    # 2000 ppm TDS at 25°C => ~1.56 bar
    pi_25c = desalination_engine.calculate_osmotic_pressure(tds_ppm=2000.0, temp_c=25.0)
    assert pi_25c == 1.56

    # Higher temperature (35°C) increases osmotic pressure
    pi_35c = desalination_engine.calculate_osmotic_pressure(tds_ppm=2000.0, temp_c=35.0)
    assert pi_35c > pi_25c

    # Zero TDS has zero osmotic pressure
    assert desalination_engine.calculate_osmotic_pressure(tds_ppm=0.0) == 0.0


def test_solar_desalination_insufficient_solar_standby(desalination_engine: SolarDesalinationEngine) -> None:
    # 0.4 kW available (below 0.75 kW threshold)
    res = desalination_engine.run_desalination_cycle(
        feed_tds_ppm=2400.0,
        feed_volume_m3=3.0,
        solar_available_kw=0.4,
    )
    assert res.status == "standby_insufficient_solar"
    assert res.total_permeate_m3 == 0.0
    assert res.energy_consumed_kwh == 0.0
    assert res.metrics.operating_pressure_bar == 0.0


def test_solar_desalination_active_run_with_erd(desalination_engine: SolarDesalinationEngine) -> None:
    # Full solar: 2.5 kW, 2,200 ppm feed TDS, 14.0 bar target
    res = desalination_engine.run_desalination_cycle(
        feed_tds_ppm=2200.0,
        feed_volume_m3=5.0,
        solar_available_kw=2.5,
        target_pressure_bar=14.0,
        use_erd=True,
    )
    assert res.status == "active_desalination"
    assert res.solar_coverage_pct >= 100.0
    assert res.metrics.operating_pressure_bar == 14.0
    assert res.metrics.salt_rejection_pct >= 99.0

    # Permeate TDS should drop from 2200 to < 25 ppm
    assert res.permeate_water.tds_ppm <= 25.0
    assert res.permeate_water.ec_ds_m <= 0.05
    assert res.is_safe_for_crops is True

    # Check recovery ratio and energy consumption with ERD
    assert res.metrics.recovery_ratio_pct == 70.0
    assert res.metrics.sec_kwh_m3 <= 1.6  # ERD reduces SEC to ~1.37 kWh/m3
    assert res.total_permeate_m3 > 0.0
    assert res.total_brine_m3 > 0.0


def test_erd_energy_recovery_comparison(desalination_engine: SolarDesalinationEngine) -> None:
    # Run with ERD enabled
    res_erd = desalination_engine.run_desalination_cycle(
        feed_tds_ppm=1800.0,
        solar_available_kw=2.4,
        use_erd=True,
    )

    # Run without ERD enabled
    res_no_erd = desalination_engine.run_desalination_cycle(
        feed_tds_ppm=1800.0,
        solar_available_kw=2.4,
        use_erd=False,
    )

    # ERD should save ~40% energy
    assert res_erd.metrics.sec_kwh_m3 < res_no_erd.metrics.sec_kwh_m3
    assert res_erd.energy_consumed_kwh < res_no_erd.energy_consumed_kwh


def test_crop_salinity_hazard_assessment(desalination_engine: SolarDesalinationEngine) -> None:
    # High salinity groundwater (1900 ppm) on sensitive strawberries (threshold 450 ppm)
    hazard_strawberries = desalination_engine.assess_crop_salinity_hazard(
        raw_tds_ppm=1900.0,
        crop_type="Strawberries",
    )
    assert hazard_strawberries["salinity_exceeded"] is True
    assert hazard_strawberries["ro_treatment_required"] is True
    assert hazard_strawberries["projected_yield_loss_pct"] > 15.0
    assert "SALINITY HAZARD" in hazard_strawberries["recommendation"]

    # Low salinity groundwater (350 ppm) on Arabica Coffee (threshold 900 ppm)
    safe_coffee = desalination_engine.assess_crop_salinity_hazard(
        raw_tds_ppm=350.0,
        crop_type="Arabica Coffee",
    )
    assert safe_coffee["salinity_exceeded"] is False
    assert safe_coffee["ro_treatment_required"] is False
    assert safe_coffee["projected_yield_loss_pct"] == 0.0
