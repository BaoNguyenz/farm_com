"""
Unit tests for Post-Harvest Cold-Chain Telemetry, Arrhenius Shelf-Life & Ethylene Kinetics.
"""

from backend.core.cold_chain import ColdChainEngine, ColdChamberState


def test_cold_chamber_optimal_storage():
    engine = ColdChainEngine()
    chamber = ColdChamberState(
        chamber_id="CHAMBER-TEST-01",
        crop_type="Strawberries",
        air_temp_c=2.5,
        relative_humidity_pct=94.0,
        ethylene_ppm=0.03,
        hours_in_storage=12.0,
    )

    proj = engine.evaluate_shelf_life(chamber)
    assert proj.remaining_shelf_life_days >= 8.0
    assert proj.freshness_index_pct >= 80.0
    assert proj.quality_grade == "AAA_PREMIUM_EXPORT"
    assert proj.respiration_rate_mg_co2_kg_h < 25.0
    assert proj.transpirational_weight_loss_pct < 1.0


def test_cold_chamber_thermal_abuse_breakdown():
    engine = ColdChainEngine()
    # Severe thermal abuse: strawberry stored at 22°C (ambient heat)
    chamber = ColdChamberState(
        chamber_id="CHAMBER-ABUSE-02",
        crop_type="Strawberries",
        air_temp_c=22.0,
        relative_humidity_pct=70.0,
        ethylene_ppm=0.15,
        hours_in_storage=48.0,
    )

    proj = engine.evaluate_shelf_life(chamber)
    # High respiration rate
    assert proj.respiration_rate_mg_co2_kg_h > 80.0
    assert proj.remaining_shelf_life_days < 2.0
    assert proj.quality_grade == "EXPEDITED_SALE_REQUIRED"
    assert "CRITICAL" in proj.alert_action


def test_ethylene_senescence_acceleration():
    engine = ColdChainEngine()
    # Baseline low ethylene
    chamber_low = ColdChamberState(crop_type="Tomatoes", ethylene_ppm=0.02, hours_in_storage=24.0)
    proj_low = engine.evaluate_shelf_life(chamber_low)

    # Elevated ethylene
    chamber_high = ColdChamberState(crop_type="Tomatoes", ethylene_ppm=0.35, hours_in_storage=24.0)
    proj_high = engine.evaluate_shelf_life(chamber_high)

    assert proj_high.ethylene_senescence_factor > proj_low.ethylene_senescence_factor
    assert proj_high.remaining_shelf_life_days < proj_low.remaining_shelf_life_days


def test_audit_all_chambers():
    engine = ColdChainEngine()
    res = engine.audit_all_chambers()
    assert "chambers" in res
    assert len(res["chambers"]) == len(engine.chambers)
    for c in res["chambers"]:
        assert c.remaining_shelf_life_days >= 0.0
