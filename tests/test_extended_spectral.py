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
