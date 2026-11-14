"""
Unit test suite for Autonomous Farm Rover Kinematics and Terramechanics.
"""
from backend.core.farm_rover import FarmRover, RoverState, RoverTask


def test_rover_initial_state() -> None:
    rover = FarmRover()
    assert rover.state.rover_id == "ROVER-ALPHA"
    assert rover.state.battery_soc == 0.85
    assert rover.state.docked is True
    assert rover.state.task == RoverTask.IDLE


def test_rover_motion_and_displacement() -> None:
    rover = FarmRover()
    # Move towards target waypoint (10.0, 10.0) for 15 seconds
    updated = rover.step_motion(target_x_m=10.0, target_y_m=10.0, duration_seconds=15.0, soil_moisture_pct=50.0)

    assert updated.docked is False
    assert updated.x_m > 0.0
    assert updated.y_m > 0.0
    assert updated.battery_soc < 0.85
    assert updated.task == RoverTask.WEEDING_PATROL


def test_rover_wheel_slip_terramechanics() -> None:
    rover = FarmRover()

    dry_slip = rover.calculate_wheel_slip(soil_moisture_pct=45.0)
    wet_slip = rover.calculate_wheel_slip(soil_moisture_pct=88.0)

    assert dry_slip == 4.0
    assert wet_slip > 30.0
    assert wet_slip > dry_slip


def test_rover_battery_failsafe_return_to_dock() -> None:
    low_batt_state = RoverState(rover_id="ROVER-LOW", battery_soc=0.205)
    rover = FarmRover(low_batt_state)

    # Motion will consume enough to drop under 0.20
    updated = rover.step_motion(target_x_m=20.0, target_y_m=20.0, duration_seconds=120.0)

    assert updated.battery_soc <= 0.20
    assert updated.task == RoverTask.RETURNING_TO_DOCK


def test_rover_dock_and_recharge() -> None:
    depleted_state = RoverState(rover_id="ROVER-CHARGE", battery_soc=0.30, x_m=15.0, y_m=15.0, docked=False)
    rover = FarmRover(depleted_state)

    recharged = rover.dock_and_recharge(charge_power_w=500.0, duration_seconds=3600.0)

    assert recharged.docked is True
    assert recharged.x_m == 0.0
    assert recharged.y_m == 0.0
    assert recharged.battery_soc > 0.30
    assert recharged.task in (RoverTask.CHARGING, RoverTask.IDLE)
