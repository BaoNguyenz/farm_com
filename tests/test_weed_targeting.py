"""
Unit test suite for Precision Weed vs Crop AI Vision and Micro-Mechanical Actuators.
"""
from backend.core.weed_targeting import (
    TargetingTool,
    WeedSpecies,
    WeedTargetingEngine,
)


def test_classify_crop_specimen_protected() -> None:
    engine = WeedTargetingEngine()
    plant = engine.classify_specimen(
        plant_id="CROP-01",
        centroid_x_mm=120.0,
        centroid_y_mm=250.0,
        canopy_diameter_mm=95.0,
        ndvi=0.82,
        aspect_ratio=1.05,
        crop_type="Strawberries",
    )

    assert plant.is_weed is False
    assert plant.species == WeedSpecies.CROP_PLANT
    assert plant.selected_tool == TargetingTool.SKIP_PROTECTED
    assert plant.termination_energy_joules == 0.0
    assert plant.glyphosate_averted_mg == 0.0


def test_classify_small_weed_laser_targeting() -> None:
    engine = WeedTargetingEngine()
    weed = engine.classify_specimen(
        plant_id="WEED-TINY",
        centroid_x_mm=45.0,
        centroid_y_mm=180.0,
        canopy_diameter_mm=16.0,  # Small weed (<25mm)
        ndvi=0.68,
        aspect_ratio=1.0,
        crop_type="Strawberries",
    )

    assert weed.is_weed is True
    assert weed.selected_tool == TargetingTool.THERMAL_LASER
    assert weed.termination_energy_joules == 15.0
    assert weed.glyphosate_averted_mg > 0.0


def test_classify_medium_weed_delta_punch() -> None:
    engine = WeedTargetingEngine()
    weed = engine.classify_specimen(
        plant_id="WEED-MED",
        centroid_x_mm=80.0,
        centroid_y_mm=320.0,
        canopy_diameter_mm=42.0,  # Medium weed (25-65mm)
        ndvi=0.74,
        aspect_ratio=1.1,
        crop_type="Strawberries",
    )

    assert weed.is_weed is True
    assert weed.selected_tool == TargetingTool.DELTA_PUNCH
    assert weed.termination_energy_joules == 35.0


def test_classify_large_weed_micro_tiller() -> None:
    engine = WeedTargetingEngine()
    weed = engine.classify_specimen(
        plant_id="WEED-LARGE",
        centroid_x_mm=150.0,
        centroid_y_mm=400.0,
        canopy_diameter_mm=75.0,  # Large clump (>65mm)
        ndvi=0.78,
        aspect_ratio=1.3,
        crop_type="Strawberries",
    )

    assert weed.is_weed is True
    assert weed.selected_tool == TargetingTool.MICRO_TILLER
    assert weed.termination_energy_joules == 75.0


def test_scan_bed_swath_and_herbicide_avoidance() -> None:
    engine = WeedTargetingEngine()

    specimens = [
        {"x_mm": 50.0, "y_mm": 100.0, "diameter_mm": 90.0, "aspect_ratio": 1.0},   # Crop
        {"x_mm": 120.0, "y_mm": 150.0, "diameter_mm": 20.0, "aspect_ratio": 1.0},  # Laser weed
        {"x_mm": 200.0, "y_mm": 220.0, "diameter_mm": 35.0, "aspect_ratio": 1.0},  # Punch weed
        {"x_mm": 300.0, "y_mm": 400.0, "diameter_mm": 40.0, "aspect_ratio": 1.0},  # Punch weed
    ]

    survey = engine.scan_bed_swath(bed_id="BED-101", specimens=specimens, crop_type="Strawberries")

    assert survey.bed_id == "BED-101"
    assert survey.total_plants_detected == 4
    assert survey.crops_count == 1
    assert survey.weeds_count == 3
    assert survey.weed_density_per_m2 > 1.5
    assert survey.action_required is True
    assert survey.total_herbicide_averted_grams > 0.0
