"""
Unit test suite for Autonomous UAV Swarm Boustrophedon Path Planning Engine.
Tests geometric decomposition, camera GSD, strip spacing, and multi-drone partitioning.
"""

import pytest

from backend.core.drone_path_planning import (
    BoustrophedonPlanner,
    CameraPayload,
    DroneUAVProfile,
    Point2D,
    SwarmPathCoordinator,
    WaypointAction,
)


def test_camera_gsd_and_strip_spacing():
    """Verify ground sampling distance (GSD) and camera strip spacing at 35m altitude."""
    camera = CameraPayload(
        sensor_width_mm=13.2,
        sensor_height_mm=8.8,
        focal_length_mm=8.8,
        image_width_px=5472,
        image_height_px=3648,
        forward_overlap_pct=75.0,
        side_overlap_pct=70.0,
    )

    gsd = camera.compute_gsd_cm_per_px(35.0)
    assert 0.8 <= gsd <= 1.2  # ~0.96 cm/pixel at 35m

    width_m, height_m = camera.compute_footprint_dimensions(35.0)
    assert width_m == 52.5
    assert height_m == 35.0

    strip_spacing = camera.compute_strip_spacing(35.0)
    # 52.5 * (1 - 0.70) = 15.75m
    assert strip_spacing == 15.75


def test_boustrophedon_single_zone_north_south():
    """Verify single zone back-and-forth sweep trajectory generation."""
    planner = BoustrophedonPlanner()
    waypoints = planner.generate_single_zone_path(
        min_x=0.0,
        max_x=60.0,
        min_y=0.0,
        max_y=100.0,
        strip_spacing=20.0,
        altitude_m=30.0,
        drone_id="UAV-Alpha",
        speed_m_s=8.0,
        sweep_direction="north_south",
    )

    assert len(waypoints) > 6
    # First waypoint must be takeoff
    assert waypoints[0].action == WaypointAction.TAKEOFF
    assert waypoints[0].z_agl == 30.0

    # Intermediate waypoints should be sweep passes or turnarounds
    actions = [w.action for w in waypoints]
    assert WaypointAction.SWEEP_PASS in actions
    assert WaypointAction.TURNAROUND in actions
    assert WaypointAction.RETURN_TO_HOME in actions
    assert waypoints[-1].action == WaypointAction.LAND
    assert waypoints[-1].z_agl == 0.0

    # Path length should be positive and realistic
    total_len = planner.calculate_path_length(waypoints)
    assert total_len > 300.0


def test_boustrophedon_single_zone_east_west():
    """Verify east-west sweep mode generation."""
    planner = BoustrophedonPlanner()
    waypoints = planner.generate_single_zone_path(
        min_x=0.0,
        max_x=120.0,
        min_y=0.0,
        max_y=50.0,
        strip_spacing=15.0,
        altitude_m=25.0,
        drone_id="UAV-Beta",
        sweep_direction="east_west",
    )

    assert len(waypoints) >= 6
    assert waypoints[0].drone_id == "UAV-Beta"
    assert waypoints[-1].action == WaypointAction.LAND


def test_swarm_voronoi_partitioning_two_drones():
    """Verify 2-drone swarm spatial partition and workload balance."""
    uav_alpha = DroneUAVProfile(
        drone_id="UAV-Alpha",
        nominal_speed_m_s=8.0,
        base_station=Point2D(x=0.0, y=0.0),
    )
    uav_beta = DroneUAVProfile(
        drone_id="UAV-Beta",
        nominal_speed_m_s=8.0,
        base_station=Point2D(x=100.0, y=0.0),
    )

    coordinator = SwarmPathCoordinator(fleet=[uav_alpha, uav_beta])
    mission = coordinator.plan_swarm_mission(
        farm_width_m=200.0,
        farm_height_m=100.0,
        altitude_m=35.0,
        wind_direction_deg=90.0,  # East wind triggers North-South sweep
    )

    assert mission.total_area_ha == 2.0
    assert len(mission.partitions) == 2
    assert "UAV-Alpha" in mission.partitions
    assert "UAV-Beta" in mission.partitions

    alpha_p = mission.partitions["UAV-Alpha"]
    beta_p = mission.partitions["UAV-Beta"]

    # Each drone gets 50% of the area (10,000 m2 each)
    assert alpha_p.area_m2 == 10000.0
    assert beta_p.area_m2 == 10000.0
    assert alpha_p.boundary_max_x == 100.0
    assert beta_p.boundary_min_x == 100.0

    assert mission.fleet_total_distance_m > 0
    assert mission.max_individual_flight_time_s > 0


def test_swarm_voronoi_partitioning_three_drones():
    """Verify 3-drone fleet partition scalability."""
    fleet = [
        DroneUAVProfile(drone_id=f"UAV-{i}", nominal_speed_m_s=7.5)
        for i in range(1, 4)
    ]
    coordinator = SwarmPathCoordinator(fleet=fleet)
    mission = coordinator.plan_swarm_mission(
        farm_width_m=300.0,
        farm_height_m=120.0,
        altitude_m=40.0,
    )

    assert len(mission.partitions) == 3
    for drone_id in ["UAV-1", "UAV-2", "UAV-3"]:
        assert drone_id in mission.partitions
        assert mission.partitions[drone_id].waypoint_count > 0


def test_wind_direction_adaptive_orientation():
    """Verify wind direction adjusts sweep line orientation."""
    drone = DroneUAVProfile(drone_id="UAV-1")
    coordinator = SwarmPathCoordinator(fleet=[drone])

    # East wind (90 deg) -> North-South sweeps (0 deg angle)
    mission_ew_wind = coordinator.plan_swarm_mission(wind_direction_deg=90.0)
    assert mission_ew_wind.sweep_angle_deg == 0.0

    # North wind (0 deg) with wide field -> East-West sweeps (90 deg angle)
    mission_n_wind = coordinator.plan_swarm_mission(
        farm_width_m=300.0,
        farm_height_m=100.0,
        wind_direction_deg=0.0,
    )
    assert mission_n_wind.sweep_angle_deg == 90.0


def test_invalid_fleet_or_altitude_error_handling():
    """Verify exceptions on empty fleet or invalid altitude."""
    with pytest.raises(ValueError, match="Fleet cannot be empty"):
        SwarmPathCoordinator(fleet=[])

    camera = CameraPayload()
    with pytest.raises(ValueError, match="Altitude must be positive"):
        camera.compute_gsd_cm_per_px(0.0)
