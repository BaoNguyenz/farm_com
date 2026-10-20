"""
Unit tests for Crop Phenology, Growing Degree Days (GDD) & dynamic Kc curves
"""
import pytest
from backend.core.crop_phenology import PhenologyEngine, PhenologicalStage


def test_daily_gdd_calculation():
    engine = PhenologyEngine(crop_name="maize")
    # Base 10C, Max 28C, Min 16C -> Mean 22C -> GDD = 12C
    gdd = engine.compute_daily_gdd(t_max=28.0, t_min=16.0)
    assert gdd == 12.0


def test_phenological_stage_advancement():
    engine = PhenologyEngine(crop_name="maize")
    assert engine.get_current_stage() == PhenologicalStage.DORMANT_SOWING

    # Advance 10 days with warm weather (15 GDD/day = 150 GDD)
    for _ in range(10):
        engine.advance_day(t_max=30.0, t_min=20.0)

    stage = engine.get_current_stage()
    assert stage in (PhenologicalStage.EMERGENCE, PhenologicalStage.TILLERING_VEGETATIVE)


def test_dynamic_kc_curve():
    engine = PhenologyEngine(crop_name="maize")
    kc_initial = engine.get_current_kc()
    assert kc_initial == 0.30

    # Simulate accumulation of 600 GDD (mid season)
    engine.accumulated_gdd = 650.0
    kc_mid = engine.get_current_kc()
    assert kc_mid >= 1.10


def test_root_depth_expansion():
    engine = PhenologyEngine(crop_name="maize")
    depth_start = engine.get_current_root_depth()
    assert 0.14 <= depth_start <= 0.16

    engine.accumulated_gdd = 1200.0
    depth_late = engine.get_current_root_depth()
    assert depth_late > 0.80
