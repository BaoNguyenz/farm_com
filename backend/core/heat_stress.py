"""
Canopy Heat Stress Assessment & Evaporative Fogging Cooling Controller.

Models thermal shock kinetics, Vapor Pressure Deficit (VPD) regulation,
and high-pressure micro-fogging pulses to protect crops from irreversible
stomatal collapse and pollen sterility during extreme midday heat.
"""

from typing import Dict, Any
import math
from pydantic import BaseModel, Field


class HeatStressAssessment(BaseModel):
    """Canopy thermal and vapor deficit diagnostics."""
    alert_level: str = Field(..., description="Classification: normal, caution, severe_heat_stress, extreme_thermal_shock")
    air_temp_c: float
    humidity_percent: float
    vpd_kpa: float = Field(..., description="Vapor Pressure Deficit in kPa")
    heat_index_c: float = Field(..., description="Biometeorological apparent heat index")
    fogging_required: bool = False
    pulse_duration_seconds: int = Field(0, description="Recommended micro-fogger duration")
    water_liters_per_zone: float = Field(0.0, description="Micro-droplet misting water requirement")
    action_summary: str


class CanopyHeatStressController:
    """
    Monitors environmental thresholds and schedules pulsed evaporative cooling.
    """

    @staticmethod
    def calculate_vpd(temp_c: float, humidity_pct: float) -> float:
        """
        Calculates Vapor Pressure Deficit (kPa) using the Tetens equation.
        """
        es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        ea = es * (max(1.0, min(100.0, humidity_pct)) / 100.0)
        return max(0.0, round(es - ea, 3))

    @staticmethod
    def calculate_heat_index(temp_c: float, rh: float) -> float:
        """
        Simplified Steadman / Rothfusz biometeorological heat index formula.
        """
        if temp_c < 26.0:
            return temp_c

        # Convert to Fahrenheit for standard NOAA formula then back to Celsius
        t_f = temp_c * 1.8 + 32.0
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * (t_f ** 2)
            - 0.05481717 * (rh ** 2)
            + 0.00122874 * (t_f ** 2) * rh
            + 0.00085282 * t_f * (rh ** 2)
            - 0.00000199 * (t_f ** 2) * (rh ** 2)
        )
        return round((hi_f - 32.0) / 1.8, 1)

    @classmethod
    def evaluate_thermal_stress(
        cls,
        air_temp_c: float,
        humidity_percent: float,
        solar_radiation_mj: float = 22.0,
        soil_moisture_pct: float = 55.0
    ) -> HeatStressAssessment:
        """
        Evaluates risk of canopy overheating and computes evaporative misting pulses.
        """
        vpd = cls.calculate_vpd(air_temp_c, humidity_percent)
        heat_idx = cls.calculate_heat_index(air_temp_c, humidity_percent)

        fogging_needed = False
        pulse_duration = 0
        water_l = 0.0
        alert_level = "normal"
        summary = "Microclimate within optimal photosynthetic range (VPD 0.8-1.4 kPa)."

        # Assessment logic:
        # Extreme thermal shock: Temp >= 36°C or (Temp >= 33°C and VPD >= 2.4 kPa)
        if air_temp_c >= 36.0 or (air_temp_c >= 33.0 and vpd >= 2.4):
            alert_level = "extreme_thermal_shock"
            fogging_needed = True
            pulse_duration = 120  # 2 minute atomized fogging pulse
            water_l = 8.5  # 8.5 Liters per 25m2 zone
            summary = (
                f"CRITICAL HEAT SHOCK: Temp {air_temp_c:.1f}°C, VPD {vpd:.2f} kPa. "
                "Canopy photosynthetic shutdown imminent. Immediate 120s evaporative fogging required."
            )
        # Severe heat stress: Temp >= 32°C or VPD >= 1.8 kPa
        elif air_temp_c >= 32.0 or vpd >= 1.8:
            alert_level = "severe_heat_stress"
            fogging_needed = True
            pulse_duration = 60  # 60s pulse
            water_l = 4.5
            summary = (
                f"HEAT STRESS ALERT: Temp {air_temp_c:.1f}°C, VPD {vpd:.2f} kPa. "
                "Stomatal conductance declining. Initiating 60s micro-fogging pulse."
            )
        # Caution: Temp >= 29°C and VPD >= 1.5 kPa
        elif air_temp_c >= 29.0 and vpd >= 1.5:
            alert_level = "caution"
            fogging_needed = False
            summary = f"Thermal caution: Temp {air_temp_c:.1f}°C, VPD {vpd:.2f} kPa. Monitoring canopy temperature."

        return HeatStressAssessment(
            alert_level=alert_level,
            air_temp_c=round(air_temp_c, 1),
            humidity_percent=round(humidity_percent, 1),
            vpd_kpa=vpd,
            heat_index_c=heat_idx,
            fogging_required=fogging_needed,
            pulse_duration_seconds=pulse_duration,
            water_liters_per_zone=water_l,
            action_summary=summary
        )

    @classmethod
    def dispatch_misting_action(
        cls,
        assessment: HeatStressAssessment,
        zone_ids: list[str],
        water_available: bool = True
    ) -> Dict[str, Any]:
        """Formulates an actionable fogging dispatcher payload."""
        if not assessment.fogging_required or not water_available:
            return {
                "action": "none",
                "fogging_active": False,
                "reason": "Fogging not required or insufficient water reserve."
            }

        total_liters = round(assessment.water_liters_per_zone * len(zone_ids), 1)
        return {
            "action": "activate_evaporative_fogging",
            "fogging_active": True,
            "target_zones": zone_ids,
            "pulse_duration_seconds": assessment.pulse_duration_seconds,
            "total_water_liters": total_liters,
            "target_vpd_reduction_kpa": 0.5,
            "expected_temp_reduction_c": 3.5,
            "alert_level": assessment.alert_level,
            "summary": assessment.action_summary
        }
