"""
Autonomous UAV Swarm Collision Avoidance, Aerodynamic Battery Cruise & RTH Engine.

Simulates multi-drone coordinated aerial operations:
- Reciprocal Velocity Obstacle (RVO) pairwise collision detection and evasive maneuvers.
- Aerodynamic drag and headwind-dependent battery power dissipation.
- Failsafe dynamic Return-To-Home (RTH) threshold calculation with wind vector compensation.
- Swarm hot-swap mission handoff when battery reserve drops below the return margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.drone_path_planning import FlightWaypoint, Point2D


class SwarmFlightStatus(str, Enum):
    """Real-time operational status of an individual UAV in the swarm."""
    SCOUTING = "scouting"
    AVOIDING_COLLISION = "avoiding_collision"
    RTH_TRIGGERED = "rth_triggered"
    RETURNING = "returning"
    LANDED = "landed"
    HANDOFF_ACTIVE = "handoff_active"


class DroneKinematicState(BaseModel):
    """Instantaneous 3D position, velocity vector, and battery state."""
    drone_id: str
    position: Point2D
    altitude_m: float = Field(35.0, ge=0.0)
    vx_m_s: float = Field(0.0, description="East velocity in m/s")
    vy_m_s: float = Field(0.0, description="North velocity in m/s")
    vz_m_s: float = Field(0.0, description="Climb/descent vertical velocity in m/s")
    battery_soc_pct: float = Field(100.0, ge=0.0, le=100.0, description="Battery State of Charge %")
    battery_capacity_wh: float = Field(160.0, gt=0.0)
    base_station: Point2D = Field(default_factory=lambda: Point2D(x=0.0, y=0.0))
    status: SwarmFlightStatus = SwarmFlightStatus.SCOUTING
    remaining_waypoints: list[FlightWaypoint] = Field(default_factory=list)

    @property
    def speed_m_s(self) -> float:
        """Horizontal ground speed."""
        return math.hypot(self.vx_m_s, self.vy_m_s)


class CollisionRiskAssessment(BaseModel):
    """Pairwise collision cone evaluation between two nearby UAVs."""
    drone_a_id: str
    drone_b_id: str
    current_distance_m: float
    time_to_closest_approach_s: float
    min_separation_distance_m: float
    collision_imminent: bool
    recommended_action: str  # "nominal", "altitude_separation", "lateral_divert"
    suggested_altitude_offset_m: float = 0.0


class RTHPowerAssessment(BaseModel):
    """Aerodynamic energy evaluation for safe return-to-home under wind conditions."""
    drone_id: str
    distance_to_home_m: float
    headwind_speed_m_s: float
    effective_ground_speed_m_s: float
    estimated_return_time_s: float
    power_draw_w: float
    required_energy_wh: float
    minimum_safe_rth_soc_pct: float
    rth_alert: bool
    reason: str


class MissionHandoffResult(BaseModel):
    """Telemetry report when a depleted drone transfers its flight plan to another."""
    exhausted_drone_id: str
    absorbing_drone_id: str
    transferred_waypoint_count: int
    handoff_successful: bool
    absorption_energy_impact_soc_pct: float


@dataclass
class SwarmSafetyEngine:
    """
    Evaluates collision cones, aerodynamic drag, and dynamic RTH triggers.
    """
    MIN_SAFE_DISTANCE_M: ClassVar[float] = 8.0
    AIR_DENSITY_KG_M3: ClassVar[float] = 1.20  # Air density at 1500m elevation (Dalat)
    DRAG_COEFFICIENT_CD: ClassVar[float] = 0.35
    DRONE_FRONTAL_AREA_M2: ClassVar[float] = 0.09
    DRONE_MASS_KG: ClassVar[float] = 2.4
    ROTOR_DISK_AREA_M2: ClassVar[float] = 0.28
    AVIONICS_POWER_W: ClassVar[float] = 22.0
    GRAVITY_M_S2: ClassVar[float] = 9.81
    RTH_SAFETY_MARGIN: ClassVar[float] = 1.25  # 25% energy contingency buffer

    def evaluate_pairwise_collision(
        self,
        drone_a: DroneKinematicState,
        drone_b: DroneKinematicState,
    ) -> CollisionRiskAssessment:
        """
        Calculates Time-To-Closest-Approach (TTCPA) using relative kinematic vectors.
        """
        dx = drone_b.position.x - drone_a.position.x
        dy = drone_b.position.y - drone_a.position.y
        dz = drone_b.altitude_m - drone_a.altitude_m
        dist_3d = math.sqrt(dx**2 + dy**2 + dz**2)

        # Relative velocity
        dvx = drone_a.vx_m_s - drone_b.vx_m_s
        dvy = drone_a.vy_m_s - drone_b.vy_m_s
        dvz = drone_a.vz_m_s - drone_b.vz_m_s
        rel_speed_sq = dvx**2 + dvy**2 + dvz**2

        # If drones are virtually stationary relative to each other
        if rel_speed_sq < 1e-4:
            collision = dist_3d < self.MIN_SAFE_DISTANCE_M
            return CollisionRiskAssessment(
                drone_a_id=drone_a.drone_id,
                drone_b_id=drone_b.drone_id,
                current_distance_m=round(dist_3d, 2),
                time_to_closest_approach_s=0.0,
                min_separation_distance_m=round(dist_3d, 2),
                collision_imminent=collision,
                recommended_action="altitude_separation" if collision else "nominal",
                suggested_altitude_offset_m=5.0 if collision else 0.0,
            )

        # Vector dot product for time of closest point of approach: tau = - (p_rel . v_rel) / |v_rel|^2
        # where p_rel = p_a - p_b = - (dx, dy, dz)
        tau = (dx * dvx + dy * dvy + dz * dvz) / rel_speed_sq

        if tau <= 0.0:
            # Drones are diverging
            min_dist = dist_3d
            collision = dist_3d < self.MIN_SAFE_DISTANCE_M
        else:
            # Converging: position at tau
            px_at_tau = dx - dvx * tau
            py_at_tau = dy - dvy * tau
            pz_at_tau = dz - dvz * tau
            min_dist = math.sqrt(px_at_tau**2 + py_at_tau**2 + pz_at_tau**2)
            collision = min_dist < self.MIN_SAFE_DISTANCE_M

        action = "nominal"
        offset_z = 0.0
        if collision:
            # Vertical altitude layering is the safest evasive maneuver for agricultural multi-rotors
            action = "altitude_separation"
            offset_z = 6.0 if drone_a.drone_id < drone_b.drone_id else -6.0

        return CollisionRiskAssessment(
            drone_a_id=drone_a.drone_id,
            drone_b_id=drone_b.drone_id,
            current_distance_m=round(dist_3d, 2),
            time_to_closest_approach_s=round(max(0.0, tau), 2),
            min_separation_distance_m=round(min_dist, 2),
            collision_imminent=collision,
            recommended_action=action,
            suggested_altitude_offset_m=offset_z,
        )

    def calculate_aerodynamic_power(
        self,
        ground_speed_m_s: float,
        wind_speed_m_s: float = 0.0,
        is_headwind: bool = True,
    ) -> float:
        """
        Computes total drone electrical power draw (Watts):
        P_total = P_hover + P_parasitic_drag + P_avionics
        """
        airspeed = (ground_speed_m_s + wind_speed_m_s) if is_headwind else max(1.0, ground_speed_m_s - wind_speed_m_s)

        # Induced hover power: W = m*g, P_ind = W * sqrt(W / (2*rho*A))
        weight_n = self.DRONE_MASS_KG * self.GRAVITY_M_S2
        induced_power = weight_n * math.sqrt(weight_n / (2.0 * self.AIR_DENSITY_KG_M3 * self.ROTOR_DISK_AREA_M2))

        # Parasitic drag power: P_drag = 0.5 * rho * Cd * A * v_air^3
        drag_power = 0.5 * self.AIR_DENSITY_KG_M3 * self.DRAG_COEFFICIENT_CD * self.DRONE_FRONTAL_AREA_M2 * (airspeed**3)

        total_power = induced_power + drag_power + self.AVIONICS_POWER_W
        return round(total_power, 2)

    def evaluate_rth_threshold(
        self,
        drone: DroneKinematicState,
        wind_speed_m_s: float = 3.5,
        wind_direction_deg: float = 0.0,  # 0 = North
    ) -> RTHPowerAssessment:
        """
        Determines if battery SoC is approaching failsafe Return-To-Home boundary
        accounting for headwind resistance on the vector pointing home.
        """
        dx_home = drone.base_station.x - drone.position.x
        dy_home = drone.base_station.y - drone.position.y
        dist_home = math.hypot(dx_home, dy_home)

        # Wind vector components
        wind_rad = math.radians(wind_direction_deg)
        wind_vx = -wind_speed_m_s * math.sin(wind_rad)
        wind_vy = -wind_speed_m_s * math.cos(wind_rad)

        # Headwind component along return vector
        unit_rx = dx_home / dist_home if dist_home > 0 else 0.0
        unit_ry = dy_home / dist_home if dist_home > 0 else 0.0
        headwind = -(wind_vx * unit_rx + wind_vy * unit_ry)

        cruise_speed = 8.0  # nominal return cruise speed
        effective_ground_speed = max(2.0, cruise_speed - max(0.0, headwind))
        return_time_s = (dist_home / effective_ground_speed) + 20.0  # +20s for vertical descent/landing

        # Power dissipation on return
        power_w = self.calculate_aerodynamic_power(
            ground_speed_m_s=effective_ground_speed,
            wind_speed_m_s=max(0.0, headwind),
            is_headwind=True,
        )

        # Required energy in Wh: P * t / 3600 * safety_margin
        required_wh = (power_w * return_time_s / 3600.0) * self.RTH_SAFETY_MARGIN
        min_safe_soc = round((required_wh / drone.battery_capacity_wh) * 100.0, 1)

        # Alert if current SoC is within 8% of minimum safe RTH SoC
        rth_needed = drone.battery_soc_pct <= (min_safe_soc + 8.0)

        reason = "nominal_reserve"
        if drone.battery_soc_pct <= min_safe_soc:
            reason = "CRITICAL_LOW_BATTERY_RTH_MANDATORY"
        elif rth_needed:
            reason = "WARNING_APPROACHING_RTH_THRESHOLD"

        return RTHPowerAssessment(
            drone_id=drone.drone_id,
            distance_to_home_m=round(dist_home, 1),
            headwind_speed_m_s=round(max(0.0, headwind), 2),
            effective_ground_speed_m_s=round(effective_ground_speed, 2),
            estimated_return_time_s=round(return_time_s, 1),
            power_draw_w=power_w,
            required_energy_wh=round(required_wh, 2),
            minimum_safe_rth_soc_pct=min_safe_soc,
            rth_alert=rth_needed,
            reason=reason,
        )

    def execute_mission_handoff(
        self,
        exhausted_drone: DroneKinematicState,
        receiving_drone: DroneKinematicState,
    ) -> MissionHandoffResult:
        """
        Transfers remaining unvisited waypoints from an exhausted drone to an available swarm peer.
        """
        unvisited = exhausted_drone.remaining_waypoints
        if not unvisited:
            return MissionHandoffResult(
                exhausted_drone_id=exhausted_drone.drone_id,
                absorbing_drone_id=receiving_drone.drone_id,
                transferred_waypoint_count=0,
                handoff_successful=True,
                absorption_energy_impact_soc_pct=0.0,
            )

        # Estimate energy required by receiving drone to cover extra waypoints
        extra_dist = 0.0
        for i in range(len(unvisited) - 1):
            extra_dist += unvisited[i].distance_to(Point2D(x=unvisited[i + 1].x, y=unvisited[i + 1].y)) if hasattr(unvisited[i], "distance_to") else math.hypot(unvisited[i + 1].x - unvisited[i].x, unvisited[i + 1].y - unvisited[i].y)

        extra_flight_time_s = extra_dist / receiving_drone.speed_m_s if receiving_drone.speed_m_s > 0 else extra_dist / 8.0
        extra_power_w = self.calculate_aerodynamic_power(8.0)
        extra_wh = (extra_power_w * extra_flight_time_s / 3600.0)
        soc_impact_pct = round((extra_wh / receiving_drone.battery_capacity_wh) * 100.0, 1)

        # Check if receiving drone has enough headroom
        can_absorb = (receiving_drone.battery_soc_pct - soc_impact_pct) >= 25.0

        if can_absorb:
            receiving_drone.remaining_waypoints.extend(unvisited)
            exhausted_drone.remaining_waypoints = []
            exhausted_drone.status = SwarmFlightStatus.RTH_TRIGGERED
            receiving_drone.status = SwarmFlightStatus.HANDOFF_ACTIVE

        return MissionHandoffResult(
            exhausted_drone_id=exhausted_drone.drone_id,
            absorbing_drone_id=receiving_drone.drone_id,
            transferred_waypoint_count=len(unvisited) if can_absorb else 0,
            handoff_successful=can_absorb,
            absorption_energy_impact_soc_pct=soc_impact_pct,
        )
