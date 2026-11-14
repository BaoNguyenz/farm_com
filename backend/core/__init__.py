"""
Digital Twin Core and Computational Agronomy Modules
"""
from backend.core.agronomy_models import (
    calculate_fao56_et0,
    calculate_gdd,
    calculate_water_deficit,
)
from backend.core.crop_phenology import (
    CropParameters,
    PhenologicalStage,
    PhenologyEngine,
)
from backend.core.dispatcher import ActionDispatcher, AuditReceipt
from backend.core.extended_spectral import (
    CanopyClassification,
    ExtendedSpectralEngine,
    SpectralBands,
)
from backend.core.farm_rover import FarmRover, RoverState, RoverTask
from backend.core.rover_fleet import (
    FleetMission,
    FleetStatusReport,
    RoverFleetCoordinator,
)
from backend.core.spectral import compute_ndvi, compute_ndwi, evaluate_crop_health
from backend.core.tick_engine import DigitalTwinTickEngine
from backend.core.twin_state import (
    ActionLog,
    FarmDigitalTwin,
    PlotZone,
    WeatherTelemetry,
    create_default_farm,
)
from backend.core.weed_targeting import (
    BedWeedSurvey,
    DetectedPlant,
    TargetingTool,
    WeedSpecies,
    WeedTargetingEngine,
)

__all__ = [
    "ActionDispatcher",
    "ActionLog",
    "AuditReceipt",
    "BedWeedSurvey",
    "CanopyClassification",
    "CropParameters",
    "DetectedPlant",
    "DigitalTwinTickEngine",
    "ExtendedSpectralEngine",
    "FarmDigitalTwin",
    "FarmRover",
    "FleetMission",
    "FleetStatusReport",
    "PhenologicalStage",
    "PhenologyEngine",
    "PlotZone",
    "RoverFleetCoordinator",
    "RoverState",
    "RoverTask",
    "SpectralBands",
    "TargetingTool",
    "WeatherTelemetry",
    "WeedSpecies",
    "WeedTargetingEngine",
    "calculate_fao56_et0",
    "calculate_gdd",
    "calculate_water_deficit",
    "compute_ndvi",
    "compute_ndwi",
    "create_default_farm",
    "evaluate_crop_health",
]
