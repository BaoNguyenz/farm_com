"""
Unit tests for Core Agronomy & Spectral Formulas (Task 1)
"""
from backend.core.spectral import compute_ndvi, compute_ndwi, compute_evi, evaluate_crop_health
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


def test_compute_evi_canopy():
    # Healthy crop canopy with high NIR, low red, low blue
    evi = compute_evi(nir=0.60, red=0.08, blue=0.03)
    assert 0.50 <= evi <= 0.90


def test_compute_evi_boundary_cases():
    # Denominator zero or both zero
    evi_zero = compute_evi(nir=0.0, red=0.0, blue=0.0)
    assert evi_zero == 0.0

    # Negative reflectance boundary check
    evi_clamped = compute_evi(nir=0.01, red=0.80, blue=0.05)
    assert -1.0 <= evi_clamped <= 0.0


def test_evaluate_crop_health_vigorous_canopy():
    res = evaluate_crop_health(ndvi=0.82, ndwi=0.45)
    assert res["status"] == "vigorous"
    assert len(res["issues"]) == 0
    assert res["ndvi"] == 0.82
    assert res["ndwi"] == 0.45


def test_evaluate_crop_health_stressed_biomass():
    res = evaluate_crop_health(ndvi=0.35, ndwi=0.25)
    assert res["status"] == "stressed"
    assert any("Low chlorophyll" in issue for issue in res["issues"])


def test_evaluate_crop_health_bare_soil():
    res = evaluate_crop_health(ndvi=0.12, ndwi=0.15)
    assert res["status"] == "bare_soil_or_dead"
    assert any("low biomass" in issue.lower() for issue in res["issues"])


def test_evaluate_crop_health_canopy_water_stress():
    # Healthy NDVI but dry canopy (NDWI < 0.10)
    res = evaluate_crop_health(ndvi=0.55, ndwi=0.02)
    assert res["status"] == "water_stressed"
    assert any("water content" in issue for issue in res["issues"])


def test_fao56_high_altitude_and_cold_climate():
    # Dalat highland at 2000m elevation during cool morning
    et0 = calculate_fao56_et0(
        temp_c=14.0,
        humidity_percent=85.0,
        wind_speed_2m_ms=1.2,
        solar_radiation_mj_m2_day=12.0,
        elevation_m=2000.0
    )
    assert 1.0 <= et0 <= 3.5


def test_fao56_extreme_arid_desert_conditions():
    # High temp, low humidity, strong wind, intense solar radiation
    et0_arid = calculate_fao56_et0(
        temp_c=38.0,
        humidity_percent=20.0,
        wind_speed_2m_ms=5.5,
        solar_radiation_mj_m2_day=26.0,
        elevation_m=200.0
    )
    assert et0_arid >= 6.5


def test_water_deficit_sufficient_precipitation():
    # Heavy monsoon rain (45mm) covering crop evapotranspiration
    deficit = calculate_water_deficit(
        et0=4.0,
        kc=1.1,
        precipitation_mm=45.0,
        soil_moisture_pct=85.0,
        target_moisture_pct=70.0
    )
    assert deficit["needs_watering"] is False
    assert deficit["recommended_irrigation_mm"] == 0.0


def test_water_deficit_moderate_soil_deficit():
    # Soil at 50% vs target 70%, no rain
    deficit = calculate_water_deficit(
        et0=5.0,
        kc=1.0,
        precipitation_mm=0.0,
        soil_moisture_pct=50.0,
        target_moisture_pct=70.0
    )
    assert deficit["needs_watering"] is True
    # Deficit is 20% * 1.5 = 30mm + ETc (5mm) = 35mm
    assert 30.0 <= deficit["recommended_irrigation_mm"] <= 40.0


def test_gdd_cold_winter_freeze():
    # Both Tmax and Tmin below base temp 10C -> zero accumulation
    gdd = calculate_gdd(t_max=8.0, t_min=2.0, t_base=10.0)
    assert gdd == 0.0


def test_gdd_extreme_summer_heat_cutoff():
    # Max temp 38C should be capped at cutoff 30C
    gdd = calculate_gdd(t_max=38.0, t_min=20.0, t_base=10.0, t_cutoff=30.0)
    # Mean of (30 + 20) / 2 = 25 -> GDD = 15
    assert gdd == 15.0
