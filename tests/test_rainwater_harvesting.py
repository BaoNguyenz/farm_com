"""
Unit test suite for Smart Rainwater Harvesting and Catchment Hydrology (Phase 18).
"""
import pytest

from backend.core.rainwater_harvesting import (
    CatchmentSurface,
    RainwaterHarvestingEngine,
)


@pytest.fixture
def rainwater_engine() -> RainwaterHarvestingEngine:
    catchment = CatchmentSurface(
        surface_id="GH_ROOF_TEST",
        area_m2=1000.0,
        runoff_coefficient=0.90,
    )
    return RainwaterHarvestingEngine(
        catchment=catchment,
        cistern_capacity_liters=100000.0,
        initial_storage_liters=20000.0,
    )


def test_peak_runoff_calculation(rainwater_engine: RainwaterHarvestingEngine) -> None:
    # 25 mm/h rainfall across 1,000 m2 with C=0.90
    # Q = (0.90 * 25 * 1000) / 1000 = 22.5 m3/h
    q_peak = rainwater_engine.calculate_peak_runoff_rate(rainfall_intensity_mm_h=25.0)
    assert q_peak == 22.5

    assert rainwater_engine.calculate_peak_runoff_rate(0.0) == 0.0


def test_zero_precipitation_event(rainwater_engine: RainwaterHarvestingEngine) -> None:
    report = rainwater_engine.process_precipitation_event(rainfall_mm=0.0)
    assert report.gross_catchment_volume_liters == 0.0
    assert report.first_flush_diverted_liters == 0.0
    assert report.net_harvested_liters == 0.0
    assert report.overflow_spilled_liters == 0.0
    assert report.cistern_storage_after.current_liters == 20000.0


def test_rain_event_first_flush_and_filtration(rainwater_engine: RainwaterHarvestingEngine) -> None:
    # 10 mm rainfall event on 1000 m2 (C=0.9)
    # Gross volume = 10 * 1000 * 0.9 = 9,000 Liters
    # First flush (1.2 mm) = 1.2 * 1000 * 0.9 = 1,080 Liters
    # Net harvested = 9000 - 1080 = 7,920 Liters
    report = rainwater_engine.process_precipitation_event(
        rainfall_mm=10.0,
        duration_hours=2.0,
        raw_turbidity_ntu=35.0,
    )

    assert report.gross_catchment_volume_liters == 9000.0
    assert report.first_flush_diverted_liters == 1080.0
    assert report.net_harvested_liters == 7920.0
    assert report.cistern_storage_after.current_liters == 27920.0
    assert report.cistern_storage_after.fill_percentage == 27.9
    assert report.overflow_spilled_liters == 0.0

    # Turbidity reduced by 88%
    assert report.water_quality.turbidity_ntu == 4.2
    assert report.water_quality.irrigation_ready is True
    assert report.water_quality.ec_ds_m <= 0.10


def test_cistern_overflow_protection() -> None:
    # Small cistern nearing capacity: 95,000 / 100,000 L
    engine = RainwaterHarvestingEngine(
        catchment=CatchmentSurface(area_m2=2000.0, runoff_coefficient=0.95),
        cistern_capacity_liters=100000.0,
        initial_storage_liters=95000.0,
    )

    # 10 mm rain on 2000 m2 (C=0.95) => Net ~ 16,720 Liters
    # Exceeds 5,000 L remaining capacity => triggers spillway overflow
    report = engine.process_precipitation_event(rainfall_mm=10.0)

    assert report.cistern_storage_after.current_liters == 100000.0
    assert report.cistern_storage_after.fill_percentage == 100.0
    assert report.cistern_storage_after.is_spilling_overflow is True
    assert report.overflow_spilled_liters > 10000.0


def test_water_withdrawal_and_summary(rainwater_engine: RainwaterHarvestingEngine) -> None:
    # Initial 20,000 L
    withdrawn = rainwater_engine.withdraw_water(5000.0)
    assert withdrawn == 5000.0
    assert rainwater_engine.current_storage_liters == 15000.0

    # Withdraw more than available
    withdrawn_excess = rainwater_engine.withdraw_water(30000.0)
    assert withdrawn_excess == 15000.0
    assert rainwater_engine.current_storage_liters == 0.0

    summary = rainwater_engine.get_system_summary()
    assert summary["current_storage_liters"] == 0.0
    assert summary["fill_percentage"] == 0.0
    assert summary["catchment_area_m2"] == 1000.0
