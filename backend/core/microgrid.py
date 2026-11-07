"""
Autonomous Agrivoltaic Micro-Grid & Battery Energy Storage (BESS) Dispatch Engine.

Models distributed solar photovoltaic (PV) generation, lithium-iron-phosphate (LFP)
battery storage kinetics, and smart load-dispatch strategies for high-efficiency farm
irrigation pumps and climate sensors.
"""

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class MicrogridMode(str, Enum):
    """Operational mode of the farm micro-grid."""
    GRID_TIED = "grid_tied"
    PEAK_SHAVING = "peak_shaving"
    ISLANDED_EMERGENCY = "islanded_emergency"


class TariffTier(str, Enum):
    """EVN Electricity Time-of-Use (TOU) tariff windows."""
    OFF_PEAK = "off_peak"
    NORMAL = "normal"
    PEAK = "peak"


class SolarPVArray(BaseModel):
    """
    Agrivoltaic Solar PV Array mounted over crops or barn rooftops.
    Models temperature-dependent efficiency and incident irradiance.
    """
    installed_capacity_kwp: float = Field(25.0, description="Nominal peak capacity in kWp")
    panel_area_m2: float = Field(120.0, description="Total active PV surface area in m²")
    stc_efficiency: float = Field(0.205, description="Standard test condition efficiency (20.5%)")
    temp_coefficient_pct: float = Field(-0.38, description="Pmax temperature coefficient (%/°C)")
    nominal_cell_temp_c: float = Field(25.0, description="Reference STC temperature (25°C)")

    def calculate_power(self, irradiance_w_m2: float, ambient_temp_c: float) -> float:
        """
        Calculate instantaneous solar power output in kW.
        Accounting for cell heating above ambient based on irradiance.
        """
        if irradiance_w_m2 <= 0.0:
            return 0.0

        # Estimated cell temperature: Tcell = Tamb + (NOCT - 20) * (G / 800)
        cell_temp_c = ambient_temp_c + (25.0 * (irradiance_w_m2 / 1000.0))
        temp_delta = cell_temp_c - self.nominal_cell_temp_c
        temp_derating = 1.0 + (self.temp_coefficient_pct / 100.0) * temp_delta
        temp_derating = max(0.6, min(1.1, temp_derating))

        # Power = Area * Irradiance * Efficiency * TempDerating
        raw_power_w = self.panel_area_m2 * irradiance_w_m2 * self.stc_efficiency * temp_derating
        power_kw = raw_power_w / 1000.0

        # Cap at inverter nominal capacity
        return min(self.installed_capacity_kwp, round(power_kw, 3))


class BatteryStorageSystem(BaseModel):
    """
    Lithium Iron Phosphate (LFP) Battery Energy Storage System (BESS).
    Models State-of-Charge (SoC), C-rate limits, and round-trip efficiency.
    """
    capacity_kwh: float = Field(40.0, description="Total nominal energy storage capacity in kWh")
    max_charge_power_kw: float = Field(12.0, description="Maximum charging rate in kW (0.3C)")
    max_discharge_power_kw: float = Field(15.0, description="Maximum discharge rate in kW")
    current_soc: float = Field(0.65, ge=0.0, le=1.0, description="State of Charge (0.0 to 1.0)")
    min_soc: float = Field(0.15, description="Reserve threshold to prevent deep discharge")
    max_soc: float = Field(0.95, description="Upper threshold to protect cell longevity")
    roundtrip_efficiency: float = Field(0.92, description="Combined inverter/battery efficiency")
    cumulative_throughput_kwh: float = Field(0.0, description="Total energy cycled through BESS")

    @property
    def stored_energy_kwh(self) -> float:
        """Usable current energy stored in kWh."""
        return self.capacity_kwh * self.current_soc

    @property
    def available_discharge_kwh(self) -> float:
        """Dischargeable energy before hitting min_soc threshold."""
        usable_soc = max(0.0, self.current_soc - self.min_soc)
        return usable_soc * self.capacity_kwh

    @property
    def available_charge_kwh(self) -> float:
        """Headroom to charge before hitting max_soc threshold."""
        room_soc = max(0.0, self.max_soc - self.current_soc)
        return room_soc * self.capacity_kwh

    def charge(self, power_kw: float, duration_hours: float = 1.0) -> tuple[float, float]:
        """
        Charge battery with available power.
        Returns (energy_accepted_kwh, curtailed_power_kw).
        """
        charge_power = min(power_kw, self.max_charge_power_kw)
        energy_attempted = charge_power * duration_hours
        effective_energy = energy_attempted * self.roundtrip_efficiency

        actual_stored = min(effective_energy, self.available_charge_kwh)
        self.current_soc = min(self.max_soc, self.current_soc + (actual_stored / self.capacity_kwh))
        self.cumulative_throughput_kwh += actual_stored

        actual_power_accepted = (actual_stored / self.roundtrip_efficiency) / duration_hours if duration_hours > 0 else 0.0
        curtailed_kw = max(0.0, power_kw - actual_power_accepted)
        return (round(actual_stored, 3), round(curtailed_kw, 3))

    def discharge(self, power_kw: float, duration_hours: float = 1.0) -> tuple[float, float]:
        """
        Discharge battery to meet load.
        Returns (energy_delivered_kwh, deficit_power_kw).
        """
        discharge_power = min(power_kw, self.max_discharge_power_kw)
        energy_attempted = discharge_power * duration_hours

        actual_delivered = min(energy_attempted, self.available_discharge_kwh * self.roundtrip_efficiency)
        energy_extracted_from_cells = actual_delivered / self.roundtrip_efficiency if self.roundtrip_efficiency > 0 else actual_delivered

        self.current_soc = max(self.min_soc, self.current_soc - (energy_extracted_from_cells / self.capacity_kwh))
        self.cumulative_throughput_kwh += energy_extracted_from_cells

        actual_power_supplied = actual_delivered / duration_hours if duration_hours > 0 else 0.0
        deficit_kw = max(0.0, power_kw - actual_power_supplied)
        return (round(actual_delivered, 3), round(deficit_kw, 3))


class MicrogridDispatchResult(BaseModel):
    """Detailed telemetry and power flow balance of a micro-grid dispatch step."""
    mode: MicrogridMode
    tariff_tier: TariffTier
    solar_power_generated_kw: float
    load_power_required_kw: float
    solar_used_directly_kw: float
    solar_to_battery_kw: float
    solar_curtailed_or_exported_kw: float
    battery_discharged_kw: float
    grid_imported_kw: float
    battery_soc_after: float
    grid_electricity_tariff_vnd_per_kwh: float
    grid_cost_vnd: float
    solar_savings_vnd: float
    carbon_avoided_kg_co2e: float


class MicrogridController:
    """
    Autonomous Energy Management System (EMS) coordinating Agrivoltaics,
    BESS, and EVN Grid connections.
    """

    # Vietnam EVN commercial/agricultural TOU tariffs (VND/kWh)
    TARIFF_RATES: ClassVar[dict[TariffTier, float]] = {
        TariffTier.OFF_PEAK: 1400.0,
        TariffTier.NORMAL: 2010.0,
        TariffTier.PEAK: 3076.0,
    }

    # Grid carbon intensity in Vietnam (kg CO2e / kWh)
    GRID_CARBON_FACTOR: ClassVar[float] = 0.7221

    def __init__(
        self,
        solar: SolarPVArray | None = None,
        battery: BatteryStorageSystem | None = None,
    ) -> None:
        self.solar = solar or SolarPVArray()
        self.battery = battery or BatteryStorageSystem()

    @classmethod
    def get_tariff_tier(cls, hour_of_day: int) -> TariffTier:
        """Determine TOU tariff tier for a given 24h clock hour."""
        # Off-peak: 22:00 - 04:00
        if hour_of_day >= 22 or hour_of_day < 4:
            return TariffTier.OFF_PEAK
        # Peak: 09:30-11:30 (approx 9-11) and 17:00-20:00 (17-19)
        elif 9 <= hour_of_day < 12 or 17 <= hour_of_day < 20:
            return TariffTier.PEAK
        # Normal daytime
        return TariffTier.NORMAL

    def dispatch(
        self,
        load_kw: float,
        irradiance_w_m2: float,
        ambient_temp_c: float,
        hour_of_day: int,
        grid_available: bool = True,
        duration_hours: float = 1.0,
    ) -> MicrogridDispatchResult:
        """
        Execute one energy dispatch cycle.
        Prioritizes:
        1. Solar PV self-consumption to power load
        2. Surplus solar to charge battery
        3. Battery discharge during peak tariff or islanded emergency
        4. Grid import as last resort (or curtailed load if grid down)
        """
        solar_gen_kw = self.solar.calculate_power(irradiance_w_m2, ambient_temp_c)
        tariff_tier = self.get_tariff_tier(hour_of_day)
        tariff_vnd = self.TARIFF_RATES[tariff_tier]

        mode = MicrogridMode.GRID_TIED
        if not grid_available:
            mode = MicrogridMode.ISLANDED_EMERGENCY
        elif tariff_tier == TariffTier.PEAK:
            mode = MicrogridMode.PEAK_SHAVING

        # Step 1: Solar covers load first
        solar_direct_kw = min(solar_gen_kw, load_kw)
        unmet_load_kw = max(0.0, load_kw - solar_direct_kw)
        excess_solar_kw = max(0.0, solar_gen_kw - solar_direct_kw)

        # Step 2: Excess solar charges BESS
        solar_to_battery_kw = 0.0
        curtailed_solar_kw = 0.0
        if excess_solar_kw > 0.0:
            stored_kwh, curtailed_kw = self.battery.charge(excess_solar_kw, duration_hours)
            solar_to_battery_kw = round(stored_kwh / duration_hours if duration_hours > 0 else 0.0, 3)
            curtailed_solar_kw = curtailed_kw

        # Step 3: Battery discharge for remaining load
        battery_discharged_kw = 0.0
        if unmet_load_kw > 0.0:
            # Discharge if peak tariff OR grid is unavailable OR high battery charge (>75%)
            should_discharge = (
                not grid_available
                or tariff_tier == TariffTier.PEAK
                or self.battery.current_soc > 0.75
            )
            if should_discharge:
                delivered_kwh, deficit_kw = self.battery.discharge(unmet_load_kw, duration_hours)
                battery_discharged_kw = round(delivered_kwh / duration_hours if duration_hours > 0 else 0.0, 3)
                unmet_load_kw = deficit_kw

        # Step 4: Grid import or unserved load
        grid_imported_kw = unmet_load_kw if grid_available else 0.0

        # Economics & environmental metrics
        total_clean_kw = solar_direct_kw + battery_discharged_kw
        grid_cost_vnd = grid_imported_kw * duration_hours * tariff_vnd
        solar_savings_vnd = total_clean_kw * duration_hours * tariff_vnd
        carbon_avoided_kg = total_clean_kw * duration_hours * self.GRID_CARBON_FACTOR

        return MicrogridDispatchResult(
            mode=mode,
            tariff_tier=tariff_tier,
            solar_power_generated_kw=solar_gen_kw,
            load_power_required_kw=round(load_kw, 3),
            solar_used_directly_kw=round(solar_direct_kw, 3),
            solar_to_battery_kw=solar_to_battery_kw,
            solar_curtailed_or_exported_kw=round(curtailed_solar_kw, 3),
            battery_discharged_kw=battery_discharged_kw,
            grid_imported_kw=round(grid_imported_kw, 3),
            battery_soc_after=round(self.battery.current_soc, 4),
            grid_electricity_tariff_vnd_per_kwh=tariff_vnd,
            grid_cost_vnd=round(grid_cost_vnd, 2),
            solar_savings_vnd=round(solar_savings_vnd, 2),
            carbon_avoided_kg_co2e=round(carbon_avoided_kg, 4),
        )
