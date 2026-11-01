"""
Water Budget & Farm Reservoir Management Engine.

Models on-site water storage dynamics, rainwater harvesting recharge,
daily extraction quotas, and drought rationing tiers for precision irrigation.
"""

from typing import Tuple
from pydantic import BaseModel, Field


class ReservoirState(BaseModel):
    """Dynamic state of farm water storage (reservoir, rainwater tank, or pond)."""
    capacity_liters: float = Field(50000.0, ge=1000.0, description="Total storage capacity in liters")
    current_storage_liters: float = Field(35000.0, ge=0.0, description="Current usable water volume in liters")
    emergency_reserve_liters: float = Field(5000.0, ge=0.0, description="Protected threshold for acute survival")
    daily_extraction_limit_liters: float = Field(15000.0, ge=500.0, description="Max sustainable daily extraction")
    daily_extracted_liters: float = Field(0.0, ge=0.0, description="Volume drawn during current 24h cycle")
    groundwater_inflow_rate_lph: float = Field(250.0, ge=0.0, description="Continuous borehole / stream inflow (L/h)")
    rainwater_catchment_m2: float = Field(600.0, ge=0.0, description="Surface area capturing precipitation")
    catchment_efficiency: float = Field(0.85, ge=0.0, le=1.0, description="Runoff coefficient")


class WaterBudgetReport(BaseModel):
    """Hydrological solvency and drought rationing status."""
    capacity_liters: float
    current_storage_liters: float
    storage_percentage: float
    available_irrigation_liters: float
    rationing_tier: str  # "abundant", "normal", "moderate_deficit", "severe_drought", "critical_empty"
    daily_quota_remaining_liters: float
    days_of_autonomy: float


class WaterBudgetManager:
    """
    Coordinates farm water allocation, recharge modeling, and rationing protocols.
    """

    def __init__(self, initial_state: ReservoirState | None = None) -> None:
        self.state = initial_state or ReservoirState()

    def step(self, elapsed_hours: float, precipitation_mm: float = 0.0) -> None:
        """
        Advances the reservoir state:
        - Adds steady groundwater inflow
        - Adds rainwater runoff: Volume = Precipitation (mm) * Catchment Area (m2) * Efficiency (1 mm * 1 m2 = 1 Liter)
        - Clamps volume to maximum capacity
        """
        if elapsed_hours <= 0.0:
            return

        # Groundwater recharge
        gw_volume = self.state.groundwater_inflow_rate_lph * elapsed_hours

        # Precipitation recharge
        rain_volume = precipitation_mm * self.state.rainwater_catchment_m2 * self.state.catchment_efficiency

        new_storage = self.state.current_storage_liters + gw_volume + rain_volume
        self.state.current_storage_liters = min(self.state.capacity_liters, max(0.0, new_storage))

    def reset_daily_extraction(self) -> None:
        """Resets the 24-hour daily extraction accumulator."""
        self.state.daily_extracted_liters = 0.0

    def evaluate_rationing_tier(self) -> str:
        """Determines the operational rationing tier based on reservoir fullness."""
        storage_pct = (self.state.current_storage_liters / self.state.capacity_liters) * 100.0

        if storage_pct >= 75.0:
            return "abundant"
        elif storage_pct >= 45.0:
            return "normal"
        elif storage_pct >= 25.0:
            return "moderate_deficit"
        elif storage_pct > 10.0:
            return "severe_drought"
        else:
            return "critical_empty"

    def request_water(self, requested_liters: float, is_emergency: bool = False) -> Tuple[bool, float, str]:
        """
        Processes an irrigation withdrawal request.
        Enforces daily extraction limits, emergency reserve preservation, and rationing reductions.

        Returns:
            (approved: bool, granted_liters: float, rationale: str)
        """
        if requested_liters <= 0.0:
            return False, 0.0, "Requested volume must be positive."

        tier = self.evaluate_rationing_tier()
        remaining_daily = max(0.0, self.state.daily_limit_remaining())
        usable_storage = max(0.0, self.state.current_storage_liters - self.state.emergency_reserve_liters)

        # Emergency override: can tap down to absolute 0 if emergency
        if is_emergency:
            available = self.state.current_storage_liters
            granted = min(requested_liters, available)
            if granted <= 0.0:
                return False, 0.0, "EMERGENCY REJECT: Reservoir completely depleted."
            self.state.current_storage_liters -= granted
            self.state.daily_extracted_liters += granted
            return True, round(granted, 1), f"EMERGENCY GRANTED: Provided {granted:.1f} L (Tier: {tier})."

        # Non-emergency checks
        if tier == "critical_empty" or usable_storage <= 0.0:
            return False, 0.0, "REJECTED: Storage at or below emergency reserve threshold (5,000 L)."

        if remaining_daily <= 0.0:
            return False, 0.0, "REJECTED: Daily extraction quota exhausted (15,000 L/day limit reached)."

        # Apply rationing scale factor
        rationing_multipliers = {
            "abundant": 1.0,
            "normal": 1.0,
            "moderate_deficit": 0.70,
            "severe_drought": 0.40,
        }
        factor = rationing_multipliers.get(tier, 0.0)
        target_allocation = requested_liters * factor
        granted = min(target_allocation, usable_storage, remaining_daily)

        self.state.current_storage_liters -= granted
        self.state.daily_extracted_liters += granted

        return True, round(granted, 1), (
            f"APPROVED: Granted {granted:.1f} L (Requested: {requested_liters:.1f} L, "
            f"Rationing factor: {factor * 100:.0f}%, Tier: {tier})."
        )

    def get_budget_report(self, avg_daily_burn_liters: float = 2500.0) -> WaterBudgetReport:
        """Compiles farm water solvency metrics."""
        storage_pct = (self.state.current_storage_liters / self.state.capacity_liters) * 100.0
        usable = max(0.0, self.state.current_storage_liters - self.state.emergency_reserve_liters)
        daily_inflow = self.state.groundwater_inflow_rate_lph * 24.0
        net_burn = max(100.0, avg_daily_burn_liters - daily_inflow)
        days_autonomy = round(usable / net_burn, 1)

        return WaterBudgetReport(
            capacity_liters=round(self.state.capacity_liters, 1),
            current_storage_liters=round(self.state.current_storage_liters, 1),
            storage_percentage=round(storage_pct, 2),
            available_irrigation_liters=round(usable, 1),
            rationing_tier=self.evaluate_rationing_tier(),
            daily_quota_remaining_liters=round(self.state.daily_limit_remaining(), 1),
            days_of_autonomy=days_autonomy
        )


def daily_limit_remaining(self: ReservoirState) -> float:
    return max(0.0, self.daily_extraction_limit_liters - self.daily_extracted_liters)

ReservoirState.daily_limit_remaining = daily_limit_remaining  # type: ignore[attr-defined]
