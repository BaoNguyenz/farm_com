"""
Unit tests for Extended Spectral Indices & Canopy Biophysical Classification
"""
import pytest
from backend.core.extended_spectral import ExtendedSpectralEngine, SpectralBands


@pytest.fixture
def sample_bands():
    return SpectralBands(
        blue=0.04,
        green=0.08,
        red=0.05,
        red_edge_1=0.18,
        red_edge_2=0.28,
        red_edge_3=0.35,
        nir=0.55,
        narrow_nir=0.56,
        swir_1=0.16,
        swir_2=0.08,
    )


def test_extended_ndvi_computation(sample_bands):
    engine = ExtendedSpectralEngine()
    ndvi = engine.compute_ndvi(sample_bands)
    assert 0.80 <= ndvi <= 0.85


def test_extended_gndvi_computation(sample_bands):
    engine = ExtendedSpectralEngine()
    gndvi = engine.compute_gndvi(sample_bands)
    assert 0.70 <= gndvi <= 0.80


def test_extended_savi_computation(sample_bands):
    engine = ExtendedSpectralEngine(soil_factor_l=0.5)
    savi = engine.compute_savi(sample_bands)
    assert 0.50 <= savi <= 0.75


def test_canopy_water_index_gao(sample_bands):
    engine = ExtendedSpectralEngine()
    ndwi = engine.compute_ndwi_gao(sample_bands)
    assert ndwi > 0.40


def test_crop_health_classification(sample_bands):
    engine = ExtendedSpectralEngine()
    indices = engine.calculate_all_indices(sample_bands)
    classification = engine.classify_crop_health(indices)
    assert classification.vigor_status == "DENSE_EXCELLENT"
    assert "OPTIMAL" in classification.water_stress_status


def test_ndre_red_edge_indices(sample_bands):
    engine = ExtendedSpectralEngine()
    ndre = engine.compute_ndre(sample_bands)
    ndre2 = engine.compute_ndre2(sample_bands)
    assert 0.40 <= ndre <= 0.60
    assert 0.25 <= ndre2 <= 0.40


def test_msavi2_soil_adjustment(sample_bands):
    engine = ExtendedSpectralEngine()
    msavi2 = engine.compute_msavi2(sample_bands)
    assert 0.50 <= msavi2 <= 0.85


def test_evi_and_evi2_consistency(sample_bands):
    engine = ExtendedSpectralEngine()
    evi = engine.compute_evi(sample_bands)
    evi2 = engine.compute_evi2(sample_bands)
    assert 0.60 <= evi <= 0.90
    assert 0.60 <= evi2 <= 0.90
    # Both formulations should yield close results for dense canopy
    assert abs(evi - evi2) < 0.20


def test_water_and_drought_indices(sample_bands):
    engine = ExtendedSpectralEngine()
    ndwi_water = engine.compute_ndwi_mcfeeters(sample_bands)
    msi = engine.compute_msi(sample_bands)
    nddi = engine.compute_nddi(sample_bands)

    # For healthy vegetation: Green < NIR, so NDWI water < 0
    assert ndwi_water < 0.0
    # MSI: SWIR / NIR < 1.0 for hydrated tissue
    assert 0.20 <= msi <= 0.40
    # NDDI: (NDVI - NDWI) / (NDVI + NDWI)
    assert -1.0 <= nddi <= 1.0


def test_chlorophyll_indices_cigreen_cirededge_mtci(sample_bands):
    engine = ExtendedSpectralEngine()
    ci_green = engine.compute_cigreen(sample_bands)
    ci_re = engine.compute_cirededge(sample_bands)
    mtci = engine.compute_mtci(sample_bands)

    assert ci_green > 4.0
    assert ci_re > 1.5
    assert mtci > 0.5


def test_canopy_water_stress_recommendation():
    engine = ExtendedSpectralEngine()
    indices = {
        "ndvi": 0.60,
        "ndwi_canopy": -0.15,  # Severe drought
        "ndre": 0.35,
    }
    classification = engine.classify_crop_health(indices)
    assert classification.water_stress_status == "SEVERE_DESICCATION"
    assert "priority irrigation" in classification.recommendation.lower()


def test_chlorosis_nutrient_deficiency_recommendation():
    engine = ExtendedSpectralEngine()
    indices = {
        "ndvi": 0.55,
        "ndwi_canopy": 0.25,
        "ndre": 0.20,  # Below 0.28 -> chlorosis
    }
    classification = engine.classify_crop_health(indices)
    assert classification.chlorophyll_status == "CHLOROSIS_DEFICIENT"
    assert "nitrogen" in classification.recommendation.lower()


def test_analyze_grid_canopy_batch():
    from backend.core.extended_spectral import analyze_grid_canopy
    cells = [
        {"blue": 0.04, "green": 0.08, "red": 0.05, "nir": 0.55, "swir_1": 0.16},
        {"blue": 0.05, "green": 0.09, "red": 0.06, "nir": 0.50, "swir_1": 0.18},
    ]
    results, summary = analyze_grid_canopy(cells)

    assert len(results) == 2
    assert summary["total_cells_analyzed"] == 2.0
    assert 0.70 <= summary["mean_ndvi"] <= 0.85
    assert summary["mean_ndwi"] > 0.30


def test_boundary_zero_reflectance_handling():
    engine = ExtendedSpectralEngine()
    zero_bands = SpectralBands(
        blue=0.0, green=0.0, red=0.0, red_edge_1=0.0, red_edge_2=0.0,
        red_edge_3=0.0, nir=0.0, narrow_nir=0.0, swir_1=0.0, swir_2=0.0
    )
    all_indices = engine.calculate_all_indices(zero_bands)
    # Ensure zero denominator never raises ZeroDivisionError and safely returns 0.0
    assert all_indices["ndvi"] == 0.0
    assert all_indices["gndvi"] == 0.0
    assert all_indices["ndre"] == 0.0
    assert all_indices["evi"] == 0.0
    assert all_indices["savi"] == 0.0


def test_soil_factor_l_variations_on_savi(sample_bands):
    engine_dry_soil = ExtendedSpectralEngine(soil_factor_l=1.0)
    engine_dense_canopy = ExtendedSpectralEngine(soil_factor_l=0.2)

    savi_l1 = engine_dry_soil.compute_savi(sample_bands)
    savi_l02 = engine_dense_canopy.compute_savi(sample_bands)

    assert savi_l1 > 0.0
    assert savi_l02 > 0.0
    assert savi_l1 != savi_l02
