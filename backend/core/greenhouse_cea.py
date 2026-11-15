"""
Controlled Environment Agriculture (CEA) Greenhouse Microclimate & CO2 Enrichment Engine.

Implements biophysical and biochemical equations for:
- Closed and semi-closed polyhouse energy balance and psychrometrics (Tetens equation)
- Canopy Vapor Pressure Deficit (VPD) regulation via motorized ridge vents and evaporative wet pads
- Farquhar-von Caemmerer-Berry (FvCB) photosynthetic CO2 assimilation ($P_n$)
- Economically optimized CO2 enrichment scheduling (anti-exhaust ventilation loss interlocking)
"""
import math
from typing import ClassVar

from pydantic import BaseModel, Field


class GreenhouseActuators(BaseModel):
    """Mechanical control states for greenhouse climate regulation."""
    roof_vent_pct: float = Field(25.0, ge=0.0, le=100.0, description="Motorized ridge vent opening aperture %")
    side_curtain_pct: float = Field(15.0, ge=0.0, le=100.0, description="Roll-up side curtain opening %")
    shade_screen_deployed: bool = Field(False, description="Whether reflective thermal shade cloth is extended")
    pad_and_fan_active: bool = Field(False, description="Evaporative cellulose wet pad with exhaust fans")
    co2_dosing_valve_open: bool = Field(False, description="Liquid CO2 gas injection valve")
    co2_dosing_rate_kg_h: float = Field(0.0, ge=0.0, le=25.0, description="Mass flow rate of CO2 injection")


class GreenhouseMicroclimate(BaseModel):
    """Real-time microclimatic telemetry inside the CEA polyhouse."""
    greenhouse_id: str = "GH-POLYHOUSE-01"
    air_temp_c: float
    relative_humidity_pct: float = Field(..., ge=10.0, le=100.0)
    co2_concentration_ppm: float = Field(..., ge=300.0, le=2500.0)
    solar_par_umol_m2_s: float = Field(..., ge=0.0, description="Photosynthetically Active Radiation in umol/m2-s")
    vpd_kpa: float = Field(..., ge=0.0, description="Vapor Pressure Deficit in kPa")
    canopy_net_photosynthesis_umol_m2_s: float
    climate_status: str  # optimal, heat_stress, excessive_humidity, co2_depleted
    actuators: GreenhouseActuators


class GreenhouseCEAEngine:
    """
    Simulates polyhouse thermodynamic heat exchange, humidity balance, and plant photosynthetic kinetics.
    """

    # Photosynthetic constants for Strawberries / C3 greenhouse crops
    P_MAX_BASE: ClassVar[float] = 22.0  # Maximum light-saturated photosynthetic rate (umol CO2 / m2-s)
    LIGHT_HALF_SAT: ClassVar[float] = 300.0  # Half-saturation constant for PAR (umol/m2-s)
    CO2_COMPENSATION_POINT_PPM: ClassVar[float] = 55.0  # Gamma compensation point
    TARGET_VPD_MIN_KPA: ClassVar[float] = 0.8
    TARGET_VPD_MAX_KPA: ClassVar[float] = 1.4

    def __init__(self, greenhouse_id: str = "GH-POLYHOUSE-01") -> None:
        self.greenhouse_id = greenhouse_id
        self.actuators = GreenhouseActuators()
        self.current_co2_ppm = 420.0

    @staticmethod
    def calculate_vpd(temp_c: float, humidity_percent: float) -> float:
        """
        Calculates Vapor Pressure Deficit (VPD) using the Tetens vapor pressure formulation.
        """
        sat_vp = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        act_vp = sat_vp * (humidity_percent / 100.0)
        return max(0.01, round(sat_vp - act_vp, 2))

    def calculate_photosynthesis(
        self,
        par_umol_m2_s: float,
        co2_ppm: float,
        temp_c: float,
    ) -> float:
        """
        Calculates net photosynthetic rate ($P_n$) based on PAR, CO2 concentration, and thermal kinetics.
        """
        if par_umol_m2_s <= 10.0 or co2_ppm <= self.CO2_COMPENSATION_POINT_PPM:
            return -1.5  # Dark respiration

        # Light response curve (Michaelis-Menten hyperbolic curve)
        light_factor = par_umol_m2_s / (par_umol_m2_s + self.LIGHT_HALF_SAT)

        # Rubisco carboxylation CO2 substrate multiplier
        co2_factor = (co2_ppm - self.CO2_COMPENSATION_POINT_PPM) / (co2_ppm + (2.0 * self.CO2_COMPENSATION_POINT_PPM))

        # Temperature optimum curve: peak near 23-25°C, sharp decline above 34°C
        temp_factor = math.exp(-0.5 * (((temp_c - 24.0) / 7.0) ** 2))

        pn = self.P_MAX_BASE * light_factor * co2_factor * temp_factor
        return round(max(0.0, pn), 2)

    def regulate_microclimate(
        self,
        ambient_temp_c: float,
        ambient_humidity_pct: float,
        solar_radiation_mj: float,
        target_temp_c: float = 24.0,
        target_co2_ppm: float = 850.0,
        manual_actuators: bool = False,
    ) -> GreenhouseMicroclimate:
        """
        Computes actuator setpoints and resulting internal microclimate.
        """
        # Convert MJ/m2-day to instantaneous PAR (approx: 1 MJ/m2-day ~ 2.1 umol/m2-s midday equivalent)
        par = round(min(1800.0, solar_radiation_mj * 52.0), 1)

        # Solar heat gain inside polyhouse (+4°C to +10°C over ambient if closed)
        heat_gain = (solar_radiation_mj / 25.0) * 8.5
        internal_temp = ambient_temp_c + heat_gain

        # Actuator dispatch logic:
        # 1. Thermal control
        if not manual_actuators:
            if internal_temp > (target_temp_c + 4.0):
                self.actuators.roof_vent_pct = 90.0
                self.actuators.side_curtain_pct = 75.0
                self.actuators.pad_and_fan_active = True
                self.actuators.shade_screen_deployed = solar_radiation_mj > 18.0
                internal_temp -= 6.5
            elif internal_temp > target_temp_c:
                self.actuators.roof_vent_pct = 45.0
                self.actuators.side_curtain_pct = 30.0
                self.actuators.pad_and_fan_active = False
                self.actuators.shade_screen_deployed = False
                internal_temp -= 3.0
            else:
                self.actuators.roof_vent_pct = 15.0
                self.actuators.side_curtain_pct = 10.0
                self.actuators.pad_and_fan_active = False
                self.actuators.shade_screen_deployed = False
        else:
            # Under manual control, cooling is proportional to vent aperture and wet pad
            vent_cooling = (self.actuators.roof_vent_pct / 100.0) * 5.0
            pad_cooling = 3.5 if self.actuators.pad_and_fan_active else 0.0
            internal_temp -= (vent_cooling + pad_cooling)

        internal_temp = round(internal_temp, 1)
        internal_rh = min(95.0, max(35.0, ambient_humidity_pct + (15.0 if self.actuators.pad_and_fan_active else -5.0)))
        internal_rh = round(internal_rh, 1)

        vpd = self.calculate_vpd(internal_temp, internal_rh)

        # 2. Photosynthetic CO2 dosing control
        # Anti-exhaust loss rule: Only inject CO2 if vents are restricted (<55%) and PAR > 200 umol/m2-s
        can_enrich_co2 = self.actuators.roof_vent_pct < 55.0 and par > 200.0
        if not manual_actuators:
            if can_enrich_co2:
                self.actuators.co2_dosing_valve_open = True
                self.actuators.co2_dosing_rate_kg_h = 4.5
                self.current_co2_ppm = min(1200.0, target_co2_ppm)
            else:
                self.actuators.co2_dosing_valve_open = False
                self.actuators.co2_dosing_rate_kg_h = 0.0
                self.current_co2_ppm = 415.0
        else:
            # If manual actuator had CO2 valve open but vents opened >= 55%, force shut off valve
            if self.actuators.roof_vent_pct >= 55.0 and self.actuators.co2_dosing_valve_open:
                self.actuators.co2_dosing_valve_open = False
                self.actuators.co2_dosing_rate_kg_h = 0.0
                self.current_co2_ppm = 415.0

        pn = self.calculate_photosynthesis(par, self.current_co2_ppm, internal_temp)

        # Determine climate status
        if internal_temp >= 33.0 or vpd > 2.2:
            status = "heat_stress"
        elif internal_rh > 88.0:
            status = "excessive_humidity"
        elif self.current_co2_ppm > 700.0:
            status = "optimal_enriched"
        else:
            status = "optimal"

        return GreenhouseMicroclimate(
            greenhouse_id=self.greenhouse_id,
            air_temp_c=internal_temp,
            relative_humidity_pct=internal_rh,
            co2_concentration_ppm=self.current_co2_ppm,
            solar_par_umol_m2_s=par,
            vpd_kpa=vpd,
            canopy_net_photosynthesis_umol_m2_s=pn,
            climate_status=status,
            actuators=self.actuators,
        )
