"""
Digital Twin Core and Computational Agronomy Modules
"""
from backend.core.spectral import compute_ndvi, compute_ndwi, evaluate_crop_health
from backend.core.agronomy_models import calculate_fao56_et0, calculate_water_deficit, calculate_gdd
from backend.core.extended_spectral import ExtendedSpectralEngine, SpectralBands, CanopyClassification
from backend.core.crop_phenology import PhenologyEngine, PhenologicalStage, CropParameters

from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherTelemetry, ActionLog, create_default_farm
from backend.core.tick_engine import DigitalTwinTickEngine
from backend.core.dispatcher import ActionDispatcher, AuditReceipt

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
    "FarmDigitalTwin",
    "PlotZone",
    "WeatherTelemetry",
    "ActionLog",
    "create_default_farm",
    "DigitalTwinTickEngine",
    "ActionDispatcher",
    "AuditReceipt",
]
