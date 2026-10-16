"""
Computational Agronomy Models
Implements FAO-56 Penman-Monteith reference evapotranspiration (ET0),
Growing Degree Days (GDD), and Soil Water Balance.
"""
import math
from typing import Dict, Any

def calculate_fao56_et0(
    temp_c: float,
    humidity_percent: float,
    wind_speed_2m_ms: float,
    solar_radiation_mj_m2_day: float,
    elevation_m: float = 1500.0
) -> float:
    """
    Computes Reference Evapotranspiration (ET0) in mm/day using FAO-56 Penman-Monteith equation.
    
    :param temp_c: Mean daily air temperature in Celsius
    :param humidity_percent: Relative humidity (%)
    :param wind_speed_2m_ms: Wind speed at 2m height (m/s)
    :param solar_radiation_mj_m2_day: Solar radiation (MJ / m^2 / day)
    :param elevation_m: Altitude above sea level in meters
    """
    # 1. Atmospheric pressure P (kPa)
    P = 101.3 * math.pow((293.0 - 0.0065 * elevation_m) / 293.0, 5.26)
    
    # 2. Psychrometric constant gamma (kPa / °C)
    gamma = 0.000665 * P
    
    # 3. Slope of saturation vapor pressure curve Delta (kPa / °C)
    temp_term = (17.27 * temp_c) / (temp_c + 237.3)
    es = 0.6108 * math.exp(temp_term) # Saturation vapor pressure (kPa)
    delta = (4098.0 * es) / math.pow(temp_c + 237.3, 2)
    
    # 4. Actual vapor pressure ea (kPa)
    ea = es * (humidity_percent / 100.0)
    
    # 5. Net radiation estimate (Rn) - Soil heat flux G is ~0 for daily calculation
    # Typical Rn is ~ 0.77 * solar_radiation_mj_m2_day - longwave losses (~ 3 MJ/m2/day)
    Rn = max(0.0, 0.77 * solar_radiation_mj_m2_day - 2.5)
    G = 0.0
    
    # 6. FAO-56 Penman-Monteith formula:
    # ET0 = (0.408 * Delta * (Rn - G) + gamma * (900 / (T + 273)) * u2 * (es - ea)) / (Delta + gamma * (1 + 0.34 * u2))
    u2 = max(0.5, wind_speed_2m_ms)
    num1 = 0.408 * delta * (Rn - G)
    num2 = gamma * (900.0 / (temp_c + 273.0)) * u2 * (es - ea)
    den = delta + gamma * (1.0 + 0.34 * u2)
    
    et0 = (num1 + num2) / den
    return float(max(0.1, round(et0, 2)))

def calculate_gdd(t_max: float, t_min: float, t_base: float = 10.0, t_cutoff: float = 30.0) -> float:
    """
    Growing Degree Days (GDD) accumulated in a single day.
    """
    t_max_adj = min(t_max, t_cutoff)
    t_min_adj = max(t_min, t_base)
    t_mean = (t_max_adj + t_min_adj) / 2.0
    gdd = max(0.0, t_mean - t_base)
    return float(round(gdd, 2))

def calculate_water_deficit(
    et0: float,
    kc: float,
    precipitation_mm: float,
    soil_moisture_pct: float,
    target_moisture_pct: float = 70.0
) -> Dict[str, Any]:
    """
    Calculates crop water requirement and irrigation recommendation.
    Crop Evapotranspiration ETc = ET0 * Kc
    """
    etc = et0 * kc
    net_water_loss = etc - precipitation_mm
    deficit_pct = max(0.0, target_moisture_pct - soil_moisture_pct)
    
    # Rule-of-thumb: 1% soil moisture deficit in 30cm root zone ~ 1.5mm water
    irrigation_needed_mm = 0.0
    if deficit_pct > 15.0 or (deficit_pct > 5.0 and net_water_loss > 0):
        irrigation_needed_mm = round((deficit_pct * 1.5) + max(0.0, net_water_loss), 1)
        
    return {
        "et0_mm": et0,
        "crop_coefficient_kc": kc,
        "crop_water_loss_etc_mm": round(etc, 2),
        "precipitation_mm": precipitation_mm,
        "soil_moisture_pct": soil_moisture_pct,
        "recommended_irrigation_mm": irrigation_needed_mm,
        "needs_watering": irrigation_needed_mm > 0.0
    }
