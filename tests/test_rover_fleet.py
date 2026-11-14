"""
Unit test suite for Autonomous Rover Fleet Swarm Coordinator.
"""
from backend.core.farm_rover import RoverTask
from backend.core.rover_fleet import RoverFleetCoordinator


def test_fleet_initialization() -> None:
    coordinator = RoverFleetCoordinator()
    status = coordinator.get_fleet_status()

    assert status.total_rovers == 4
    assert status.docked_count == 4
    assert status.active_patrolling_count == 0
    assert status.average_battery_soc > 0.80
    assert len(status.rovers) == 4


def test_dispatch_mission_success() -> None:
    coordinator = RoverFleetCoordinator()

    mission = coordinator.dispatch_mission(plot_id="Z_0_1", row_index=2, priority="urgent_infestation")

    assert mission.target_plot_id == "Z_0_1"
    assert mission.target_row_index == 2
    assert mission.assigned_rover_id is not None
    assert mission.priority == "urgent_infestation"

    assigned_rover = coordinator.rovers[mission.assigned_rover_id]
    assert assigned_rover.state.task == RoverTask.WEEDING_PATROL
    assert assigned_rover.state.docked is False


def test_recall_all_to_dock() -> None:
    coordinator = RoverFleetCoordinator()
    coordinator.dispatch_mission(plot_id="Z_0_2", row_index=1)

    recalled = coordinator.recall_all_to_dock()

    for s in recalled:
        assert s.task == RoverTask.RETURNING_TO_DOCK
        assert s.assigned_plot_id is None


def test_step_fleet_cycle_simulation() -> None:
    coordinator = RoverFleetCoordinator()
    mission = coordinator.dispatch_mission(plot_id="Z_1_1", row_index=1)

    rover_id = mission.assigned_rover_id
    assert rover_id is not None
    initial_weeds = coordinator.rovers[rover_id].state.weeds_eradicated_count

    # Simulate 2 minutes of field weeding
    status = coordinator.step_fleet_cycle(duration_seconds=120.0, soil_moisture_pct=58.0)

    assert status.active_patrolling_count >= 1
    assert coordinator.rovers[rover_id].state.weeds_eradicated_count > initial_weeds
    assert status.total_herbicide_saved_kg >= 0.0
