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

    @staticmethod
    def estimate_extraterrestrial_radiation(
        latitude_deg: float, day_of_year: int
    ) -> float:
        """Calculates extraterrestrial daily solar radiation Ra (MJ/m2/day)."""
        lat_rad = (math.pi / 180.0) * latitude_deg
        dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year)
        solar_declination = 0.409 * math.sin(((2.0 * math.pi / 365.0) * day_of_year) - 1.39)

        term = -math.tan(lat_rad) * math.tan(solar_declination)
        clamped_term = max(-1.0, min(1.0, term))
        sunset_hour_angle = math.acos(clamped_term)

        solar_constant = 0.0820  # MJ / m^2 / min
        gsc_factor = (24.0 * 60.0 / math.pi) * solar_constant

        ra = gsc_factor * dr * (
            sunset_hour_angle * math.sin(lat_rad) * math.sin(solar_declination)
            + math.cos(lat_rad) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
        return max(0.0, ra)

    @staticmethod
    def estimate_solar_radiation_hargreaves(
        t_max: float, t_min: float, ra_mj: float, coastal: bool = False
    ) -> float:
        """Hargreaves-Samani method for solar radiation Rs when pyranometer is missing."""
        kr = 0.19 if coastal else 0.16
        delta_t = max(0.0, t_max - t_min)
        rs = kr * math.sqrt(delta_t) * ra_mj
        return round(rs, 2)

    @staticmethod
    def assess_frost_hazard(
        temp_c: float, dew_point_c: float, wind_speed_ms: float
    ) -> Optional[MicroclimateRiskAlert]:
        """Detects advective or radiation frost risks for vulnerable blossoms."""
        if temp_c > 3.0:
            return None

        if temp_c <= 0.0:
            if wind_speed_ms < 1.5:
                return MicroclimateRiskAlert(
                    severity="CRITICAL",
                    category="FROST",
                    headline="Radiation Frost in Effect (Zero Wind Inversion)",
                    advisory_action="Activate overhead sprinkler frost protection or wind machines."
                )
            else:
                return MicroclimateRiskAlert(
                    severity="HIGH",
                    category="FREEZE",
                    headline="Advective Freeze Event with Active Wind Chill",
                    advisory_action="Deploy row covers, fleece, or thermal heaters."
                )
        elif temp_c <= 2.5 and dew_point_c <= 0.0:
            return MicroclimateRiskAlert(
                severity="WARNING",
                category="FROST_PROBABLE",
                headline="Sub-Freezing Ground Radiation Inversion Expected",
                advisory_action="Monitor soil thermometers and prep frost countermeasures."
            )
        return None

    @staticmethod
    def assess_spray_drift_hazard(
        wind_speed_ms: float, temp_c: float, rh_pct: float
    ) -> Dict[str, object]:
        """Evaluates agrochemical spray drift window based on atmospheric stability."""
        # Convert m/s to km/h
        wind_kmh = wind_speed_ms * 3.6

        if wind_kmh < 3.0:
            status = "DANGEROUS_TEMPERATURE_INVERSION"
            safe = False
            msg = "Air is too calm. Atmospheric inversion likely causes airborne droplet drift."
        elif wind_kmh <= 15.0:
            if temp_c > 30.0 or rh_pct < 40.0:
                status = "RAPID_DROPLET_EVAPORATION"
                safe = False
                msg = "High temperature / low humidity will cause droplets to evaporate before canopy contact."
            else:
                status = "IDEAL_SPRAY_WINDOW"
                safe = True
                msg = "Favorable wind speed and adequate humidity for uniform droplet deposition."
        elif wind_kmh <= 20.0:
            status = "MARGINAL_HIGH_DRIFT_RISK"
            safe = False
            msg = "Use drift-reducing coarse nozzles and reduce boom height."
        else:
            status = "EXCESSIVE_WIND_PROHIBITED"
            safe = False
            msg = "Spray operation suspended due to severe off-target drift hazard."

        return {
            "wind_speed_kmh": round(wind_kmh, 1),
            "spray_permitted": safe,
            "classification": status,
            "recommendation": msg,
