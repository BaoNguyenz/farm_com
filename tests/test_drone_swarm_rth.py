"""
Unit test suite for UAV Swarm Collision Avoidance, Aerodynamic Battery Cruise, and RTH Failsafe.
"""

from backend.core.drone_path_planning import FlightWaypoint, Point2D, WaypointAction
from backend.core.drone_swarm_rth import (
    DroneKinematicState,
    SwarmFlightStatus,
    SwarmSafetyEngine,
)


def test_pairwise_collision_detection_head_on():
    """Verify collision cone detection when two drones fly head-on."""
    engine = SwarmSafetyEngine()

    # Drone A at (0, 50, 35m) moving East at 8 m/s
    drone_a = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=0.0, y=50.0),
        altitude_m=35.0,
        vx_m_s=8.0,
        vy_m_s=0.0,
    )
    # Drone B at (40, 50, 35m) moving West at 8 m/s
    drone_b = DroneKinematicState(
        drone_id="UAV-Beta",
        position=Point2D(x=40.0, y=50.0),
        altitude_m=35.0,
        vx_m_s=-8.0,
        vy_m_s=0.0,
    )

    assessment = engine.evaluate_pairwise_collision(drone_a, drone_b)

    assert assessment.current_distance_m == 40.0
    # Relative speed = 16 m/s, so time to collision is 40 / 16 = 2.5 s
    assert 2.4 <= assessment.time_to_closest_approach_s <= 2.6
    assert assessment.min_separation_distance_m < 1.0  # direct collision point
    assert assessment.collision_imminent is True
    assert assessment.recommended_action == "altitude_separation"
    assert abs(assessment.suggested_altitude_offset_m) == 6.0


def test_diverging_drones_no_collision():
    """Verify no collision alert when drones are flying away from each other."""
    engine = SwarmSafetyEngine()

    drone_a = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=10.0, y=20.0),
        vx_m_s=-5.0,
    )
    drone_b = DroneKinematicState(
        drone_id="UAV-Beta",
        position=Point2D(x=30.0, y=20.0),
        vx_m_s=5.0,
    )

    assessment = engine.evaluate_pairwise_collision(drone_a, drone_b)
    assert assessment.collision_imminent is False
    assert assessment.recommended_action == "nominal"


def test_aerodynamic_power_drag_scaling():
    """Verify aerodynamic power scales with speed and headwind due to cubic airspeed drag."""
    engine = SwarmSafetyEngine()

    power_hover = engine.calculate_aerodynamic_power(ground_speed_m_s=0.0, wind_speed_m_s=0.0)
    power_cruise = engine.calculate_aerodynamic_power(ground_speed_m_s=8.0, wind_speed_m_s=0.0)
    power_headwind = engine.calculate_aerodynamic_power(ground_speed_m_s=8.0, wind_speed_m_s=6.0, is_headwind=True)

    assert power_hover > 50.0  # induced hover power
    assert power_cruise > power_hover
    assert power_headwind > power_cruise  # extra headwind drag


def test_rth_threshold_evaluation_nominal():
    """Verify drone close to base with full battery has no RTH alert."""
    engine = SwarmSafetyEngine()
    drone = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=10.0, y=10.0),
        base_station=Point2D(x=0.0, y=0.0),
        battery_soc_pct=95.0,
        battery_capacity_wh=160.0,
    )

    rth = engine.evaluate_rth_threshold(drone, wind_speed_m_s=2.0)
    assert rth.rth_alert is False
    assert rth.minimum_safe_rth_soc_pct < 15.0
    assert rth.reason == "nominal_reserve"


def test_rth_threshold_evaluation_critical_headwind():
    """Verify RTH triggers when battery is critically depleted against headwind."""
    engine = SwarmSafetyEngine()
    drone = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=0.0, y=300.0),  # 300m North of base
        base_station=Point2D(x=0.0, y=0.0),
        battery_soc_pct=14.0,  # low battery
        battery_capacity_wh=160.0,
    )

    # South wind blowing North means returning South encounters headwind
    rth = engine.evaluate_rth_threshold(drone, wind_speed_m_s=6.0, wind_direction_deg=180.0)
    assert rth.rth_alert is True
    assert "CRITICAL" in rth.reason or "WARNING" in rth.reason
    assert rth.distance_to_home_m == 300.0


def test_mission_handoff_success():
    """Verify depleted drone successfully hands off remaining waypoints to capable peer."""
    engine = SwarmSafetyEngine()

    unvisited = [
        FlightWaypoint(index=5, x=120.0, y=80.0, z_agl=35.0, action=WaypointAction.SWEEP_PASS),
        FlightWaypoint(index=6, x=120.0, y=120.0, z_agl=35.0, action=WaypointAction.SWEEP_PASS),
        FlightWaypoint(index=7, x=140.0, y=120.0, z_agl=35.0, action=WaypointAction.SWEEP_PASS),
    ]

    exhausted = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=100.0, y=80.0),
        battery_soc_pct=15.0,
        remaining_waypoints=list(unvisited),
    )

    receiver = DroneKinematicState(
        drone_id="UAV-Beta",
        position=Point2D(x=90.0, y=80.0),
        battery_soc_pct=80.0,  # lots of battery
        remaining_waypoints=[],
    )

    result = engine.execute_mission_handoff(exhausted, receiver)

    assert result.handoff_successful is True
    assert result.transferred_waypoint_count == 3
    assert len(exhausted.remaining_waypoints) == 0
    assert len(receiver.remaining_waypoints) == 3
    assert exhausted.status == SwarmFlightStatus.RTH_TRIGGERED
    assert receiver.status == SwarmFlightStatus.HANDOFF_ACTIVE


def test_mission_handoff_insufficient_peer_battery():
    """Verify handoff is safely rejected if the receiving drone also lacks battery headroom."""
    engine = SwarmSafetyEngine()

    unvisited = [
        FlightWaypoint(index=i, x=float(i * 30), y=50.0, z_agl=35.0)
        for i in range(10)
    ]

    exhausted = DroneKinematicState(
        drone_id="UAV-Alpha",
        position=Point2D(x=50.0, y=50.0),
        battery_soc_pct=12.0,
        remaining_waypoints=unvisited,
    )

    receiver = DroneKinematicState(
        drone_id="UAV-Beta",
        position=Point2D(x=50.0, y=50.0),
        battery_soc_pct=22.0,  # below minimum 25% safe reserve
        remaining_waypoints=[],
    )

    result = engine.execute_mission_handoff(exhausted, receiver)
    assert result.handoff_successful is False
    assert result.transferred_waypoint_count == 0
