"""
Unit tests for Water Budget and Reservoir Management Engine.
Validates hydrological simulation, groundwater & rainfall recharge,
drought rationing tiers, daily quota enforcement, and emergency overrides.
"""

from backend.core.water_budget import (
    ReservoirState,
    WaterBudgetManager,
    WaterBudgetReport,
)


def test_reservoir_recharge_dynamics():
    state = ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=20000.0,
        groundwater_inflow_rate_lph=200.0,
        rainwater_catchment_m2=500.0,
        catchment_efficiency=0.80
    )
    mgr = WaterBudgetManager(state)

    # 10 hours elapsed with 10 mm rainfall
    # Expected groundwater: 200 * 10 = 2,000 L
    # Expected rainwater: 10 mm * 500 m2 * 0.80 = 4,000 L
    # Total expected: 20,000 + 2,000 + 4,000 = 26,000 L
    mgr.step(elapsed_hours=10.0, precipitation_mm=10.0)

    assert abs(mgr.state.current_storage_liters - 26000.0) < 0.1


def test_water_rationing_tiers():
    mgr = WaterBudgetManager(ReservoirState(capacity_liters=10000.0, current_storage_liters=8000.0))
    assert mgr.evaluate_rationing_tier() == "abundant"

    mgr.state.current_storage_liters = 5500.0
    assert mgr.evaluate_rationing_tier() == "normal"

    mgr.state.current_storage_liters = 3000.0
    assert mgr.evaluate_rationing_tier() == "moderate_deficit"

    mgr.state.current_storage_liters = 1500.0
    assert mgr.evaluate_rationing_tier() == "severe_drought"

    mgr.state.current_storage_liters = 500.0
    assert mgr.evaluate_rationing_tier() == "critical_empty"


def test_water_request_normal_and_rationed():
    # In moderate deficit tier (30% storage), allocation is scaled by 0.70
    mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=15000.0,  # 30% -> moderate_deficit
        emergency_reserve_liters=5000.0
    ))

    approved, granted, rationale = mgr.request_water(1000.0, is_emergency=False)
    assert approved is True
    assert granted == 700.0  # 1000 * 0.70
    assert "70%" in rationale
    assert mgr.state.current_storage_liters == 14300.0


def test_water_request_daily_limit_exhaustion():
    mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=40000.0,
        daily_extraction_limit_liters=2000.0,
        daily_extracted_liters=1800.0
    ))

    # Request 500L when only 200L remaining in daily quota
    approved, granted, _ = mgr.request_water(500.0, is_emergency=False)
    assert approved is True
    assert granted == 200.0
    assert mgr.state.daily_limit_remaining() == 0.0

    # Next request must be rejected
    approved_next, granted_next, reason = mgr.request_water(100.0, is_emergency=False)
    assert approved_next is False
    assert granted_next == 0.0
    assert "quota exhausted" in reason.lower()


def test_water_emergency_override():
    # Reservoir at 4,000 L, below the 5,000 L emergency threshold
    mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=4000.0,
        emergency_reserve_liters=5000.0
    ))

    # Routine request is rejected
    appr_norm, grant_norm, reason_norm = mgr.request_water(500.0, is_emergency=False)
    assert appr_norm is False
    assert grant_norm == 0.0
    assert "emergency reserve" in reason_norm.lower()

    # Emergency request bypasses reserve protection
    appr_emg, grant_emg, reason_emg = mgr.request_water(500.0, is_emergency=True)
    assert appr_emg is True
    assert grant_emg == 500.0
    assert "EMERGENCY GRANTED" in reason_emg
    assert mgr.state.current_storage_liters == 3500.0


def test_water_budget_report():
    mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=35000.0,
        emergency_reserve_liters=5000.0,
        groundwater_inflow_rate_lph=100.0  # 2,400 L/day
    ))

    report = mgr.get_budget_report(avg_daily_burn_liters=3400.0)
    assert isinstance(report, WaterBudgetReport)
    assert report.capacity_liters == 50000.0
    assert report.current_storage_liters == 35000.0
    assert report.storage_percentage == 70.0
    assert report.available_irrigation_liters == 30000.0
    assert report.rationing_tier == "normal"
    # Net burn = 3400 - 2400 = 1000 L/day. Usable = 30000 -> 30 days autonomy
    assert report.days_of_autonomy == 30.0
