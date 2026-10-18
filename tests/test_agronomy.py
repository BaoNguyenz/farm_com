"""
Unit tests for Core Agronomy & Spectral Formulas (Task 1)
"""
import pytest
from backend.core.spectral import compute_ndvi, compute_ndwi, evaluate_crop_health
from backend.core.agronomy_models import calculate_fao56_et0, calculate_water_deficit, calculate_gdd

def test_compute_ndvi_healthy_vegetation():
    # Dense healthy canopy: high NIR, low Red
    ndvi = compute_ndvi(nir=0.60, red=0.08)
    assert 0.70 <= ndvi <= 0.80

def test_compute_ndvi_division_by_zero():
    # Boundary case: both zero
    ndvi = compute_ndvi(nir=0.0, red=0.0)
    assert ndvi == 0.0

def test_compute_ndwi_water_content():
    # Hydrated canopy: NIR > SWIR
    ndwi = compute_ndwi(nir=0.55, swir=0.15)
    assert ndwi > 0.40

def test_fao56_penman_monteith_typical_day():
    # Typical warm sunny day in Da Lat / highland area
    et0 = calculate_fao56_et0(
        temp_c=25.0,
        humidity_percent=65.0,
        wind_speed_2m_ms=2.0,
        solar_radiation_mj_m2_day=18.0,
        elevation_m=1500.0
    )
    # Reference ET0 should be in realistic 3.5mm - 5.5mm range
    assert 3.5 <= et0 <= 5.5

def test_water_deficit_triggers_irrigation():
    deficit = calculate_water_deficit(
        et0=4.5,
        kc=1.05,
        precipitation_mm=0.0,
        soil_moisture_pct=35.0,
        target_moisture_pct=70.0
    )
    assert deficit["needs_watering"] is True
    assert deficit["recommended_irrigation_mm"] > 0

def test_gdd_calculation():
    # Base temperature 10C, day max 28C, min 16C -> mean 22C -> GDD = 12C
    gdd = calculate_gdd(t_max=28.0, t_min=16.0, t_base=10.0)
    assert gdd == 12.0
