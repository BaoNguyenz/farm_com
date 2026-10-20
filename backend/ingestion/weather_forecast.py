"""
Agro-Meteorological Forecast Engine and Microclimate Transformer.
Calculates Vapor Pressure Deficit (VPD), Hargreaves-Samani solar radiation,
frost risk assessment, and spray drift hazard indices for precision farming.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class HourlyWeatherData:
    """Hourly atmospheric observation or model forecast."""
    timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_ms: float
    solar_radiation_wm2: float
    precipitation_mm: float
    surface_pressure_hpa: float = 1013.25


@dataclass
class MicroclimateRiskAlert:
    """Actionable weather risk alert for farm operators."""
    severity: str
    category: str
    headline: str
    advisory_action: str


class WeatherAnalyticsEngine:
    """Performs atmospheric calculations for precision agricultural operations."""

    @staticmethod
    def calculate_saturation_vapor_pressure(temp_c: float) -> float:
        """Tetens formula for saturation vapor pressure es(T) in kPa."""
        return 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    @staticmethod
    def calculate_actual_vapor_pressure(temp_c: float, rh_pct: float) -> float:
        """Actual vapor pressure ea in kPa from relative humidity."""
        es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(temp_c)
        return es * (max(0.0, min(100.0, rh_pct)) / 100.0)

    @staticmethod
    def calculate_vpd(temp_c: float, rh_pct: float) -> float:
        """Vapor Pressure Deficit (VPD) in kPa: difference between es and ea."""
        es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(temp_c)
        ea = WeatherAnalyticsEngine.calculate_actual_vapor_pressure(temp_c, rh_pct)
        return max(0.0, es - ea)

    @staticmethod
    def classify_vpd_range(vpd_kpa: float) -> str:
        """Classifies VPD for greenhouse and open-field stomatal conductance."""
        if vpd_kpa < 0.4:
            return "TOO_HUMID_FUNGAL_RISK"
        elif vpd_kpa <= 0.8:
            return "LOW_OPTIMAL_PROPAGATION"
        elif vpd_kpa <= 1.2:
            return "HEALTHY_VEGETATIVE_SWEETSPOT"
        elif vpd_kpa <= 1.6:
            return "TRANSIT_WATER_CONSERVING"
        else:
            return "STOMATAL_CLOSURE_DROUGHT_STRESS"

