"""
Autonomous UAV Swarm Cooperative Scouting & Boustrophedon Path Planning Engine.

Provides geometric decomposition, multi-drone spatial partitioning, and optimal
flight trajectory generation for agricultural multispectral aerial surveys:
- Boustrophedon Cellular Decomposition for complete area coverage (back-and-forth sweep).
- Strip spacing calculation based on camera Field-of-View (FOV), flight altitude, and overlap.
- Ground Sampling Distance (GSD) resolution estimation.
- Multi-UAV Voronoi-based spatial partitioning to balance mission workloads across fleet.
- Wind and solar illumination orientation optimization to reduce turns and prevent camera flare.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class WaypointAction(str, Enum):
    """Action to execute at a navigation waypoint."""
    TAKEOFF = "takeoff"
    CRUISE = "cruise"
    SWEEP_PASS = "sweep_pass"
    TURNAROUND = "turnaround"
    CAMERA_CAPTURE = "camera_capture"
    RETURN_TO_HOME = "return_to_home"
    LAND = "land"


class Point2D(BaseModel):
    """2D metric coordinates (meters) in farm local cartesian frame."""
    x: float = Field(..., description="East coordinate in meters")
    y: float = Field(..., description="North coordinate in meters")

    def distance_to(self, other: Point2D) -> float:
        """Euclidean distance to another point."""
        return math.hypot(self.x - other.x, self.y - other.y)


class FlightWaypoint(BaseModel):
    """3D aerial waypoint with speed, sensor triggers, and mission tags."""
    index: int
    x: float = Field(..., description="East coordinate in meters")
    y: float = Field(..., description="North coordinate in meters")
    z_agl: float = Field(..., description="Altitude Above Ground Level in meters")
    action: WaypointAction = WaypointAction.SWEEP_PASS
    speed_m_s: float = Field(8.0, ge=1.0, le=25.0)
    trigger_camera: bool = True
    drone_id: str = "UAV-Alpha"


class CameraPayload(BaseModel):
    """Optical / multispectral sensor specifications for aerial mapping."""
    sensor_width_mm: float = Field(13.2, description="Sensor physical width in mm (1-inch sensor)")
    sensor_height_mm: float = Field(8.8, description="Sensor physical height in mm")
    focal_length_mm: float = Field(8.8, description="Lens focal length in mm")
    image_width_px: int = Field(5472, description="Horizontal image pixel resolution")
    image_height_px: int = Field(3648, description="Vertical image pixel resolution")
    forward_overlap_pct: float = Field(75.0, ge=50.0, le=90.0, description="In-track image overlap")
    side_overlap_pct: float = Field(70.0, ge=40.0, le=85.0, description="Cross-track lane overlap")

    def compute_gsd_cm_per_px(self, altitude_m: float) -> float:
        """Calculate Ground Sampling Distance (GSD) in cm/pixel."""
        if altitude_m <= 0:
            raise ValueError("Altitude must be positive")
        # GSD_h = (altitude * sensor_width) / (focal_length * image_width) * 100
        gsd_h = (altitude_m * self.sensor_width_mm) / (self.focal_length_mm * self.image_width_px) * 100.0
        return round(gsd_h, 2)

    def compute_footprint_dimensions(self, altitude_m: float) -> tuple[float, float]:
        """Compute ground coverage width (cross-track) and height (in-track) in meters."""
        width_m = (self.sensor_width_mm * altitude_m) / self.focal_length_mm
        height_m = (self.sensor_height_mm * altitude_m) / self.focal_length_mm
        return round(width_m, 2), round(height_m, 2)

    def compute_strip_spacing(self, altitude_m: float) -> float:
        """Calculate distance between adjacent flight lines (meters)."""
        width_m, _ = self.compute_footprint_dimensions(altitude_m)
        spacing = width_m * (1.0 - (self.side_overlap_pct / 100.0))
        return max(2.0, round(spacing, 2))


class DroneUAVProfile(BaseModel):
    """Physical and operational envelope of an agricultural drone platform."""
    drone_id: str
    nominal_speed_m_s: float = Field(8.0, ge=2.0, le=20.0)
    survey_altitude_m: float = Field(35.0, ge=10.0, le=120.0)
    battery_capacity_wh: float = Field(160.0, description="Battery energy in Watt-hours")
    base_station: Point2D = Field(default_factory=lambda: Point2D(x=0.0, y=0.0))
    camera: CameraPayload = Field(default_factory=CameraPayload)


class PartitionPlan(BaseModel):
    """Spatial survey sector allocated to a specific drone."""
    drone_id: str
    boundary_min_x: float
    boundary_max_x: float
    boundary_min_y: float
    boundary_max_y: float
    area_m2: float
    estimated_distance_m: float
    estimated_time_s: float
    waypoint_count: int
    waypoints: list[FlightWaypoint] = Field(default_factory=list)


class SwarmSurveyMission(BaseModel):
    """Complete cooperative swarm aerial survey mission plan."""
    mission_id: str
    farm_width_m: float
    farm_height_m: float
    total_area_ha: float
    altitude_m: float
    gsd_cm_per_px: float
    strip_spacing_m: float
    sweep_angle_deg: float
    partitions: dict[str, PartitionPlan]
    fleet_total_distance_m: float
    max_individual_flight_time_s: float


@dataclass
class BoustrophedonPlanner:
    """
    Decomposes rectangular agricultural zones into Boustrophedon parallel sweep strips.
    """
    DEFAULT_ALTITUDE_M: ClassVar[float] = 35.0

    def generate_single_zone_path(
        self,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
        strip_spacing: float,
        altitude_m: float,
        drone_id: str = "UAV-Alpha",
        speed_m_s: float = 8.0,
        home_pos: Point2D | None = None,
        sweep_direction: str = "north_south",  # "north_south" or "east_west"
    ) -> list[FlightWaypoint]:
        """
        Generates alternating back-and-forth sweep waypoints with takeoff and return legs.
        """
        waypoints: list[FlightWaypoint] = []
        home = home_pos or Point2D(x=min_x, y=min_y)

        idx = 0
        # 1. Takeoff & Climb to survey altitude at home position
        waypoints.append(
            FlightWaypoint(
                index=idx,
                x=home.x,
                y=home.y,
                z_agl=altitude_m,
                action=WaypointAction.TAKEOFF,
                speed_m_s=3.0,
                trigger_camera=False,
                drone_id=drone_id,
            )
        )
        idx += 1

        if sweep_direction == "north_south":
            # Strip lines along X axis, moving Y back and forth
            x_current = min_x + (strip_spacing / 2.0)
            direction_up = True

            while x_current <= max_x:
                if direction_up:
                    y_start, y_end = min_y, max_y
                else:
                    y_start, y_end = max_y, min_y

                # Start of strip pass
                waypoints.append(
                    FlightWaypoint(
                        index=idx,
                        x=round(x_current, 2),
                        y=round(y_start, 2),
                        z_agl=altitude_m,
                        action=WaypointAction.SWEEP_PASS,
                        speed_m_s=speed_m_s,
                        trigger_camera=True,
                        drone_id=drone_id,
                    )
                )
                idx += 1

                # End of strip pass
                waypoints.append(
                    FlightWaypoint(
                        index=idx,
                        x=round(x_current, 2),
                        y=round(y_end, 2),
                        z_agl=altitude_m,
                        action=WaypointAction.SWEEP_PASS,
                        speed_m_s=speed_m_s,
                        trigger_camera=True,
                        drone_id=drone_id,
                    )
                )
                idx += 1

                # Turnaround step to next lane
                next_x = min(x_current + strip_spacing, max_x)
                if next_x > x_current:
                    waypoints.append(
                        FlightWaypoint(
                            index=idx,
                            x=round(next_x, 2),
                            y=round(y_end, 2),
                            z_agl=altitude_m,
                            action=WaypointAction.TURNAROUND,
                            speed_m_s=speed_m_s * 0.7,
                            trigger_camera=False,
                            drone_id=drone_id,
                        )
                    )
                    idx += 1

                x_current += strip_spacing
                direction_up = not direction_up
        else:
            # East-West sweeps: Strip lines along Y axis, moving X back and forth
            y_current = min_y + (strip_spacing / 2.0)
            direction_right = True

            while y_current <= max_y:
                if direction_right:
                    x_start, x_end = min_x, max_x
                else:
                    x_start, x_end = max_x, min_x

                waypoints.append(
                    FlightWaypoint(
                        index=idx,
                        x=round(x_start, 2),
                        y=round(y_current, 2),
                        z_agl=altitude_m,
                        action=WaypointAction.SWEEP_PASS,
                        speed_m_s=speed_m_s,
                        trigger_camera=True,
                        drone_id=drone_id,
                    )
                )
                idx += 1

                waypoints.append(
                    FlightWaypoint(
                        index=idx,
                        x=round(x_end, 2),
                        y=round(y_current, 2),
                        z_agl=altitude_m,
                        action=WaypointAction.SWEEP_PASS,
                        speed_m_s=speed_m_s,
                        trigger_camera=True,
                        drone_id=drone_id,
                    )
                )
                idx += 1

                next_y = min(y_current + strip_spacing, max_y)
                if next_y > y_current:
                    waypoints.append(
                        FlightWaypoint(
                            index=idx,
                            x=round(x_end, 2),
                            y=round(next_y, 2),
                            z_agl=altitude_m,
                            action=WaypointAction.TURNAROUND,
                            speed_m_s=speed_m_s * 0.7,
                            trigger_camera=False,
                            drone_id=drone_id,
                        )
                    )
                    idx += 1

                y_current += strip_spacing
                direction_right = not direction_right

        # Return to Home leg
        waypoints.append(
            FlightWaypoint(
                index=idx,
                x=home.x,
                y=home.y,
                z_agl=altitude_m,
                action=WaypointAction.RETURN_TO_HOME,
                speed_m_s=speed_m_s,
                trigger_camera=False,
                drone_id=drone_id,
            )
        )
        idx += 1

        # Landing
        waypoints.append(
            FlightWaypoint(
                index=idx,
                x=home.x,
                y=home.y,
                z_agl=0.0,
                action=WaypointAction.LAND,
                speed_m_s=2.0,
                trigger_camera=False,
                drone_id=drone_id,
            )
        )

        return waypoints

    @staticmethod
    def calculate_path_length(waypoints: list[FlightWaypoint]) -> float:
        """Computes total 3D metric path length across waypoints."""
        if len(waypoints) < 2:
            return 0.0
        dist = 0.0
        for i in range(len(waypoints) - 1):
            w1, w2 = waypoints[i], waypoints[i + 1]
            dist += math.sqrt((w2.x - w1.x) ** 2 + (w2.y - w1.y) ** 2 + (w2.z_agl - w1.z_agl) ** 2)
        return round(dist, 2)


class SwarmPathCoordinator:
    """
    Coordinates multi-UAV survey missions across agricultural perimeters.
    Partitions the area into balanced sub-regions based on fleet composition.
    """

    def __init__(self, fleet: list[DroneUAVProfile]) -> None:
        if not fleet:
            raise ValueError("Fleet cannot be empty")
        self.fleet = fleet
        self.planner = BoustrophedonPlanner()

    def plan_swarm_mission(
        self,
        farm_width_m: float = 200.0,
        farm_height_m: float = 150.0,
        altitude_m: float = 35.0,
        wind_direction_deg: float = 0.0,  # 0 = North, 90 = East
    ) -> SwarmSurveyMission:
        """
        Partitions the rectangular boundary among drones and generates parallel sweeps.
        Selects sweep direction perpendicular to wind to minimize drift, or along longest edge.
        """
        k = len(self.fleet)
        total_area_m2 = farm_width_m * farm_height_m
        total_area_ha = round(total_area_m2 / 10000.0, 3)

        # Optimize sweep direction: if wind is predominantly East/West (45-135 or 225-315),
        # prefer North-South sweeps to fly crosswind or along wind.
        if (45.0 <= wind_direction_deg <= 135.0) or (225.0 <= wind_direction_deg <= 315.0):
            sweep_dir = "north_south"
            sweep_angle = 0.0
        else:
            sweep_dir = "east_west" if farm_width_m > farm_height_m else "north_south"
            sweep_angle = 90.0 if sweep_dir == "east_west" else 0.0

        # Uniform 1D Voronoi slice along the primary dimension
        # If sweep is North-South, divide X axis into k slices
        partitions: dict[str, PartitionPlan] = {}
        total_dist = 0.0
        max_duration = 0.0

        camera = self.fleet[0].camera
        gsd = camera.compute_gsd_cm_per_px(altitude_m)
        strip_spacing = camera.compute_strip_spacing(altitude_m)

        if sweep_dir == "north_south":
            slice_width = farm_width_m / k
            for i, drone in enumerate(self.fleet):
                sub_min_x = i * slice_width
                sub_max_x = (i + 1) * slice_width
                sub_min_y = 0.0
                sub_max_y = farm_height_m
                sub_area = (sub_max_x - sub_min_x) * (sub_max_y - sub_min_y)

                wps = self.planner.generate_single_zone_path(
                    min_x=sub_min_x,
                    max_x=sub_max_x,
                    min_y=sub_min_y,
                    max_y=sub_max_y,
                    strip_spacing=strip_spacing,
                    altitude_m=altitude_m,
                    drone_id=drone.drone_id,
                    speed_m_s=drone.nominal_speed_m_s,
                    home_pos=drone.base_station,
                    sweep_direction=sweep_dir,
                )
                dist = self.planner.calculate_path_length(wps)
                duration = round(dist / drone.nominal_speed_m_s, 1)

                total_dist += dist
                max_duration = max(max_duration, duration)

                partitions[drone.drone_id] = PartitionPlan(
                    drone_id=drone.drone_id,
                    boundary_min_x=round(sub_min_x, 1),
                    boundary_max_x=round(sub_max_x, 1),
                    boundary_min_y=round(sub_min_y, 1),
                    boundary_max_y=round(sub_max_y, 1),
                    area_m2=round(sub_area, 1),
                    estimated_distance_m=dist,
                    estimated_time_s=duration,
                    waypoint_count=len(wps),
                    waypoints=wps,
                )
        else:
            # Slices along Y axis
            slice_height = farm_height_m / k
            for i, drone in enumerate(self.fleet):
                sub_min_x = 0.0
                sub_max_x = farm_width_m
                sub_min_y = i * slice_height
                sub_max_y = (i + 1) * slice_height
                sub_area = (sub_max_x - sub_min_x) * (sub_max_y - sub_min_y)

                wps = self.planner.generate_single_zone_path(
                    min_x=sub_min_x,
                    max_x=sub_max_x,
                    min_y=sub_min_y,
                    max_y=sub_max_y,
                    strip_spacing=strip_spacing,
                    altitude_m=altitude_m,
                    drone_id=drone.drone_id,
                    speed_m_s=drone.nominal_speed_m_s,
                    home_pos=drone.base_station,
                    sweep_direction=sweep_dir,
                )
                dist = self.planner.calculate_path_length(wps)
                duration = round(dist / drone.nominal_speed_m_s, 1)

                total_dist += dist
                max_duration = max(max_duration, duration)

                partitions[drone.drone_id] = PartitionPlan(
                    drone_id=drone.drone_id,
                    boundary_min_x=round(sub_min_x, 1),
                    boundary_max_x=round(sub_max_x, 1),
                    boundary_min_y=round(sub_min_y, 1),
                    boundary_max_y=round(sub_max_y, 1),
                    area_m2=round(sub_area, 1),
                    estimated_distance_m=dist,
                    estimated_time_s=duration,
                    waypoint_count=len(wps),
                    waypoints=wps,
                )

        return SwarmSurveyMission(
            mission_id=f"SWARM-MSN-{int(altitude_m)}M-{k}UAV",
            farm_width_m=farm_width_m,
            farm_height_m=farm_height_m,
            total_area_ha=total_area_ha,
            altitude_m=altitude_m,
            gsd_cm_per_px=gsd,
            strip_spacing_m=strip_spacing,
            sweep_angle_deg=sweep_angle,
            partitions=partitions,
            fleet_total_distance_m=round(total_dist, 2),
            max_individual_flight_time_s=max_duration,
        )
