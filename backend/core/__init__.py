"""
Digital Twin Core and Computational Agronomy Modules
"""
from backend.core.spectral import compute_ndvi, compute_ndwi, evaluate_crop_health
from backend.core.agronomy_models import calculate_fao56_et0, calculate_water_deficit, calculate_gdd
from backend.core.extended_spectral import ExtendedSpectralEngine, SpectralBands, CanopyClassification
from backend.core.crop_phenology import PhenologyEngine, PhenologicalStage, CropParameters

__all__ = [
    "compute_ndvi",
    "compute_ndwi",
    "evaluate_crop_health",
    "calculate_fao56_et0",
    "calculate_water_deficit",
    "calculate_gdd",
    "ExtendedSpectralEngine",
    "SpectralBands",
    "CanopyClassification",
    "PhenologyEngine",
    "PhenologicalStage",
    "CropParameters",
]
