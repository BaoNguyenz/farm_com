"""
Autonomous Farm Ground Vehicle (AGV / Rover) Kinematics & Battery Dynamics Engine.

Implements physical and electrochemical equations for:
- 4WD differential-drive rover kinematics across agricultural furrows
- Muddy soil terramechanics: Bekker wheel slip as a function of soil moisture
- LiFePO4 battery pack discharge dynamics and solar charging dock integration
- Automatic fail-safe return-to-base on critical low state-of-charge (<20%)
"""
import math
from enum import Enum

from pydantic import BaseModel, Field


class RoverTask(str, Enum):
    IDLE = "IDLE"
    WEEDING_PATROL = "WEEDING_PATROL"
    RETURNING_TO_DOCK = "RETURNING_TO_DOCK"
    CHARGING = "CHARGING"
    EMERGENCY_HALT = "EMERGENCY_HALT"


class RoverState(BaseModel):
    """Telemetry state of an individual agricultural field rover."""
    rover_id: str = "ROVER-ALPHA"
    x_m: float = Field(0.0, description="X coordinate in farm grid (meters)")
    y_m: float = Field(0.0, description="Y coordinate in farm grid (meters)")
    speed_m_s: float = Field(0.8, ge=0.0, le=2.5, description="Cruise velocity in m/s")
    battery_soc: float = Field(0.85, ge=0.0, le=1.0, description="Battery State of Charge [0.0 - 1.0]")
    battery_capacity_wh: float = Field(1200.0, ge=100.0, description="Total battery pack capacity in Wh")
    wheel_slip_pct: float = Field(0.0, ge=0.0, le=100.0, description="Tire rotational slip in soil")
    task: RoverTask = RoverTask.IDLE
    weeds_eradicated_count: int = Field(0, ge=0)
    docked: bool = True
    assigned_plot_id: str | None = None


class FarmRover:
    """
    Simulates kinematics, power consumption, and soil mobility for an agricultural weeding rover.
    """

    BASE_MOTOR_POWER_W: float = 140.0
    WEEDING_ACTUATOR_POWER_W: float = 85.0
    DOCK_X_M: float = 0.0
    DOCK_Y_M: float = 0.0

    def __init__(self, state: RoverState | None = None) -> None:
        self.state = state or RoverState()

    def calculate_wheel_slip(self, soil_moisture_pct: float) -> float:
        """
        Calculates Bekker terramechanics tire slip based on soil plastic limit.
        Dry loam (<65%): minimal slip (3-6%).
        Saturated clay/loam (>75%): high slip up to 45%.
        """
        if soil_moisture_pct <= 60.0:
            return 4.0
        elif soil_moisture_pct <= 75.0:
            return round(4.0 + (soil_moisture_pct - 60.0) * 0.8, 1)
        else:
            excess = soil_moisture_pct - 75.0
            return round(min(55.0, 16.0 + (excess * 2.2)), 1)

    def step_motion(
        self,
        target_x_m: float,
        target_y_m: float,
        duration_seconds: float = 60.0,
        soil_moisture_pct: float = 55.0,
        is_weeding: bool = True,
    ) -> RoverState:
        """
        Simulates displacement towards waypoint factoring in wheel slip and battery drawdown.
        """
        slip_pct = self.calculate_wheel_slip(soil_moisture_pct)
        self.state.wheel_slip_pct = slip_pct

        dx = target_x_m - self.state.x_m
        dy = target_y_m - self.state.y_m
        dist_to_target = math.hypot(dx, dy)

        if dist_to_target < 0.1:
            self.state.speed_m_s = 0.0
            return self.state

        # Effective velocity reduced by tire slip
        eff_speed = self.state.speed_m_s * (1.0 - (slip_pct / 100.0))
        dist_traveled = min(dist_to_target, eff_speed * duration_seconds)

        # Update coordinates
        ratio = dist_traveled / dist_to_target if dist_to_target > 0 else 0.0
        self.state.x_m = round(self.state.x_m + (dx * ratio), 2)
        self.state.y_m = round(self.state.y_m + (dy * ratio), 2)
        self.state.docked = False

        # Power calculation: locomotion + slip traction overhead + weeding tool
        traction_multiplier = 1.0 + (slip_pct / 50.0)
        power_w = self.BASE_MOTOR_POWER_W * traction_multiplier
        if is_weeding:
            power_w += self.WEEDING_ACTUATOR_POWER_W

        energy_used_wh = (power_w * duration_seconds) / 3600.0
        soc_loss = energy_used_wh / self.state.battery_capacity_wh
        self.state.battery_soc = max(0.0, round(self.state.battery_soc - soc_loss, 4))

        # Battery fail-safe threshold (20% SoC triggers return-to-dock)
        if self.state.battery_soc <= 0.20:
            self.state.task = RoverTask.RETURNING_TO_DOCK
        elif is_weeding:
            self.state.task = RoverTask.WEEDING_PATROL

        return self.state

    def dock_and_recharge(
        self,
        charge_power_w: float = 400.0,
        duration_seconds: float = 1800.0,
    ) -> RoverState:
        """
        Charges rover battery at solar dock.
        """
        self.state.x_m = self.DOCK_X_M
        self.state.y_m = self.DOCK_Y_M
        self.state.docked = True
        self.state.speed_m_s = 0.0

        energy_in_wh = (charge_power_w * duration_seconds) / 3600.0
        soc_gain = energy_in_wh / self.state.battery_capacity_wh
        self.state.battery_soc = min(1.0, round(self.state.battery_soc + soc_gain, 4))

        if self.state.battery_soc >= 0.95:
            self.state.task = RoverTask.IDLE
        else:
            self.state.task = RoverTask.CHARGING

        return self.state
