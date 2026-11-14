"""
Multi-Rover Autonomous Fleet Coordinator & Inter-Row Swarm Dispatcher.

Orchestrates a cooperative swarm of field weeding ground robots (AGVs):
- Dispatching rovers to target plot furrows based on proximity & battery SoC
- Coordinated collision-free furrow traversal
- Automatic fleet recall during rainstorms or low-battery conditions
- Tracking farm-wide cumulative mechanical weeding statistics & herbicide avoidance
"""
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.farm_rover import FarmRover, RoverState, RoverTask


class FleetMission(BaseModel):
    """Mission dispatch command for a designated plot furrow."""
    mission_id: str
    target_plot_id: str
    target_row_index: int
    waypoint_x_m: float
    waypoint_y_m: float
    priority: str = "routine_patrol"  # urgent_infestation, routine_patrol
    assigned_rover_id: str | None = None
    completed: bool = False


class FleetStatusReport(BaseModel):
    """Consolidated telemetry and operational KPIs for the entire robot swarm."""
    total_rovers: int
    active_patrolling_count: int
    docked_count: int
    total_weeds_eradicated: int
    total_herbicide_saved_kg: float
    average_battery_soc: float = Field(..., ge=0.0, le=1.0)
    rovers: list[RoverState]


class RoverFleetCoordinator:
    """
    Central scheduler and mission controller for the autonomous robot fleet.
    """

    # Grid spacing: each plot is 5m x 5m, spaced along farm coordinate axes
    PLOT_COORDINATES: ClassVar[dict[str, tuple[float, float]]] = {
        "Z_0_0": (5.0, 5.0),
        "Z_0_1": (12.0, 5.0),
        "Z_0_2": (19.0, 5.0),
        "Z_1_0": (5.0, 12.0),
        "Z_1_1": (12.0, 12.0),
        "Z_1_2": (19.0, 12.0),
    }

    def __init__(self) -> None:
        self.rovers: dict[str, FarmRover] = {
            "ROVER-ALPHA": FarmRover(RoverState(rover_id="ROVER-ALPHA", battery_soc=0.92, docked=True)),
            "ROVER-BETA": FarmRover(RoverState(rover_id="ROVER-BETA", battery_soc=0.88, docked=True)),
            "ROVER-GAMMA": FarmRover(RoverState(rover_id="ROVER-GAMMA", battery_soc=0.84, docked=True)),
            "ROVER-DELTA": FarmRover(RoverState(rover_id="ROVER-DELTA", battery_soc=0.79, docked=True)),
        }
        self.active_missions: dict[str, FleetMission] = {}

    def get_fleet_status(self) -> FleetStatusReport:
        """Computes aggregate swarm health, active missions, and environmental savings."""
        states = [r.state for r in self.rovers.values()]
        active = sum(1 for s in states if s.task == RoverTask.WEEDING_PATROL)
        docked = sum(1 for s in states if s.docked)
        total_weeds = sum(s.weeds_eradicated_count for s in states)
        # 45 mg glyphosate avoided per weed = 0.045 g = 0.000045 kg
        total_herbicide_kg = round(total_weeds * 0.000045, 4)
        avg_soc = round(sum(s.battery_soc for s in states) / len(states), 3)

        return FleetStatusReport(
            total_rovers=len(states),
            active_patrolling_count=active,
            docked_count=docked,
            total_weeds_eradicated=total_weeds,
            total_herbicide_saved_kg=total_herbicide_kg,
            average_battery_soc=avg_soc,
            rovers=states,
        )

    def dispatch_mission(
        self,
        plot_id: str,
        row_index: int = 1,
        priority: str = "routine_patrol",
    ) -> FleetMission:
        """
        Dispatches the best available rover (highest SoC, closest to plot) to a target plot.
        """
        base_x, base_y = self.PLOT_COORDINATES.get(plot_id, (10.0, 10.0))
        target_x = base_x + (row_index * 0.8)
        target_y = base_y

        mission_id = f"MIS-{plot_id}-R{row_index}"

        # Candidate selection: available rovers with battery >= 30%
        candidates = [
            r for r in self.rovers.values()
            if r.state.battery_soc >= 0.30 and r.state.task in (RoverTask.IDLE, RoverTask.CHARGING)
        ]

        if not candidates:
            # Fallback to any rover not currently in critical emergency
            candidates = [r for r in self.rovers.values() if r.state.battery_soc >= 0.25]

        if not candidates:
            raise RuntimeError("All rovers currently depleted or returning to dock. Dispatch unavailable.")

        # Pick candidate with highest battery
        selected_rover = max(candidates, key=lambda r: r.state.battery_soc)
        selected_rover.state.task = RoverTask.WEEDING_PATROL
        selected_rover.state.assigned_plot_id = plot_id
        selected_rover.state.docked = False

        mission = FleetMission(
            mission_id=mission_id,
            target_plot_id=plot_id,
            target_row_index=row_index,
            waypoint_x_m=target_x,
            waypoint_y_m=target_y,
            priority=priority,
            assigned_rover_id=selected_rover.state.rover_id,
            completed=False,
        )
        self.active_missions[mission_id] = mission
        return mission

    def recall_all_to_dock(self) -> list[RoverState]:
        """Emergency fleet recall to solar charging base."""
        for r in self.rovers.values():
            r.state.task = RoverTask.RETURNING_TO_DOCK
            r.state.assigned_plot_id = None
        return [r.state for r in self.rovers.values()]

    def step_fleet_cycle(
        self,
        duration_seconds: float = 60.0,
        soil_moisture_pct: float = 55.0,
    ) -> FleetStatusReport:
        """
        Simulates one operational step for all active rovers in the field.
        """
        for r in self.rovers.values():
            if r.state.task == RoverTask.WEEDING_PATROL:
                # Move towards assigned mission coordinates
                target_x = 12.0
                target_y = 12.0
                for m in self.active_missions.values():
                    if m.assigned_rover_id == r.state.rover_id and not m.completed:
                        target_x = m.waypoint_x_m
                        target_y = m.waypoint_y_m
                        break

                r.step_motion(
                    target_x_m=target_x,
                    target_y_m=target_y,
                    duration_seconds=duration_seconds,
                    soil_moisture_pct=soil_moisture_pct,
                    is_weeding=True,
                )
                # Increment weed terminations
                r.state.weeds_eradicated_count += 4

            elif r.state.task == RoverTask.RETURNING_TO_DOCK:
                # Return towards dock (0.0, 0.0)
                r.step_motion(
                    target_x_m=0.0,
                    target_y_m=0.0,
                    duration_seconds=duration_seconds,
                    soil_moisture_pct=soil_moisture_pct,
                    is_weeding=False,
                )
                if r.state.x_m <= 0.2 and r.state.y_m <= 0.2:
                    r.dock_and_recharge(charge_power_w=400.0, duration_seconds=duration_seconds)

            elif r.state.task in (RoverTask.CHARGING, RoverTask.IDLE) and r.state.docked:
                r.dock_and_recharge(charge_power_w=400.0, duration_seconds=duration_seconds)

        return self.get_fleet_status()
