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
