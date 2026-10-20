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


def test_rice_crop_parameters():
    engine = PhenologyEngine(crop_name="rice")
    assert engine.params.crop_name == "Paddy Rice"
    assert engine.params.base_temperature == 10.0
    assert engine.params.kc_initial == 1.05
    assert engine.params.kc_mid == 1.20
    assert engine.params.max_root_depth_meters == 0.60


def test_coffee_crop_parameters():
    engine = PhenologyEngine(crop_name="coffee")
    assert "Coffee" in engine.params.crop_name
    assert engine.params.base_temperature == 12.0
    assert engine.params.gdd_maturity == 2200.0


def test_unknown_crop_defaults_to_maize():
    engine = PhenologyEngine(crop_name="exotic_crop_xyz")
    assert engine.params.crop_name == "Maize / Corn"


def test_late_season_kc_decline():
    engine = PhenologyEngine(crop_name="maize")
    # Total maturity GDD is 1450. At 1350 GDD, fraction > 0.80 (late stage)
    engine.accumulated_gdd = 1350.0
    kc_late = engine.get_current_kc()
    # Should decline below peak mid Kc (1.20) towards kc_end (0.35)
    assert kc_late < 1.0
    assert kc_late >= 0.35


def test_yield_response_water_deficit_penalty():
    engine = PhenologyEngine(crop_name="maize")

    # In flowering stage (most vulnerable, Ky = 1.5)
    engine.accumulated_gdd = 800.0
    assert engine.get_current_stage() == PhenologicalStage.BOOTING_FLOWERING

    # 40% water deficit (water stress ratio = 0.60)
    loss = engine.calculate_yield_response_factor(water_stress_ratio=0.60)
    # Deficit = 0.40 * Ky (1.5) * 100 = 60% loss
    assert 55.0 <= loss <= 65.0

    # Zero water deficit -> zero loss
    no_loss = engine.calculate_yield_response_factor(water_stress_ratio=1.0)
    assert no_loss == 0.0


def test_full_season_phenological_simulation():
    engine = PhenologyEngine(crop_name="maize")
    stages_visited = set()

    # Simulate 120 days of growing season with warm days
    for day in range(120):
        engine.advance_day(t_max=29.0, t_min=17.0)
        stages_visited.add(engine.get_current_stage())

    # Should have traversed through initial, vegetative, flowering to maturity
    assert PhenologicalStage.DORMANT_SOWING in stages_visited
    assert PhenologicalStage.BOOTING_FLOWERING in stages_visited
    assert engine.days_since_planting == 120
    assert engine.accumulated_gdd > 1400.0


def test_diagnostic_state_structure():
    engine = PhenologyEngine(crop_name="maize")
    engine.advance_day(t_max=28.0, t_min=18.0)
    state = engine.get_diagnostic_state()

    assert state["crop_name"] == "Maize / Corn"
    assert state["days_since_planting"] == 1
    assert "thermal_progress_percent" in state
    assert "current_stage" in state
    assert "current_kc" in state
    assert "root_depth_meters" in state


def test_extreme_temperature_boundaries_on_daily_gdd():
    engine = PhenologyEngine(crop_name="maize")
    # Subzero temperature -> 0 GDD
    assert engine.compute_daily_gdd(t_max=-5.0, t_min=-15.0) == 0.0

    # Scorching heat (45C max, 32C min) capped at 30C cutoff
    gdd = engine.compute_daily_gdd(t_max=45.0, t_min=32.0)
    # Tmax capped at 30, Tmin = 32 -> Mean = 31 -> GDD = 31 - 10 = 21.0
    assert gdd > 0.0


def test_root_growth_increases_monotonically():
    engine = PhenologyEngine(crop_name="maize")
    depths = []
    for g in [100.0, 300.0, 600.0, 900.0, 1200.0, 1450.0]:
        engine.accumulated_gdd = g
        depths.append(engine.get_current_root_depth())

    # Ensure root depth never shrinks as plant matures
    for i in range(len(depths) - 1):
        assert depths[i] <= depths[i + 1]
