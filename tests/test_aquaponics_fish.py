"""
Unit test suite for fish bio-energetics, TAN excretion, and Emerson ammonia equilibrium.
"""
import pytest

from backend.core.aquaponics_fish import (
    FishBioenergeticsEngine,
    FishSpecies,
    FishTankState,
)


def test_unionized_ammonia_emerson_equation():
    """Verify that toxic un-ionized NH3 fraction increases sharply with pH and temperature."""
    temp_c = 26.0

    # At pH 6.8 (aquaponics optimal for plants): toxic NH3 fraction is very low (~0.4%)
    f_low_ph = FishBioenergeticsEngine.calculate_unionized_ammonia_fraction(ph=6.8, temp_c=temp_c)
    # At pH 8.0 (alkaline): toxic NH3 fraction is ~5.3%
    f_high_ph = FishBioenergeticsEngine.calculate_unionized_ammonia_fraction(ph=8.0, temp_c=temp_c)

    assert f_low_ph < f_high_ph
    assert 0.002 < f_low_ph < 0.007
    assert 0.04 < f_high_ph < 0.07

    # Toxic concentration from 1.0 mg/L TAN
    nh3_acidic = FishBioenergeticsEngine.calculate_toxic_nh3_concentration(tan_mg_l=1.0, ph=6.8, temp_c=temp_c)
    nh3_alkaline = FishBioenergeticsEngine.calculate_toxic_nh3_concentration(tan_mg_l=1.0, ph=8.0, temp_c=temp_c)
    assert nh3_acidic < 0.01
    assert nh3_alkaline > 0.04


def test_daily_feeding_requirement_temperature():
    """Verify temperature-dependent feed intake for Tilapia."""
    biomass_kg = 200.0

    # At 26C (optimal): 2.0% of 200 kg = 4.0 kg feed
    feed_opt = FishBioenergeticsEngine.calculate_daily_feeding_requirement(biomass_kg=biomass_kg, water_temp_c=26.0, base_rate_pct=2.0)
    assert feed_opt == 4.0

    # At 16C (cold stress): reduced to 30% of base rate
    feed_cold = FishBioenergeticsEngine.calculate_daily_feeding_requirement(biomass_kg=biomass_kg, water_temp_c=16.0, base_rate_pct=2.0)
    assert feed_cold < feed_opt
    assert pytest.approx(feed_cold, abs=0.1) == 1.2


def test_tan_excretion_protein_fraction():
    """Verify aquaculture nitrogen excretion from protein catabolism."""
    # 2.0 kg of 32% crude protein feed
    tan_g = FishBioenergeticsEngine.calculate_tan_excretion(feed_kg=2.0, crude_protein_pct=32.0)
    # 2.0 * 32.0 * 0.092 * 10 = 58.88 g TAN
    assert pytest.approx(tan_g, abs=0.01) == 58.88

    # Zero feed -> zero TAN
    assert FishBioenergeticsEngine.calculate_tan_excretion(feed_kg=0.0) == 0.0


def test_respiratory_oxygen_consumption():
    """Verify fish metabolic oxygen demand increases post feeding."""
    biomass_kg = 250.0

    o2_resting = FishBioenergeticsEngine.calculate_respiratory_oxygen_demand(
        biomass_kg=biomass_kg, duration_hours=2.0, post_feeding_spike=False
    )
    o2_feeding = FishBioenergeticsEngine.calculate_respiratory_oxygen_demand(
        biomass_kg=biomass_kg, duration_hours=2.0, post_feeding_spike=True
    )

    assert o2_resting < o2_feeding
    # Resting: 250 * 250 * 2 / 1000 = 125.0 g
    assert pytest.approx(o2_resting, abs=0.1) == 125.0
    # Feeding: 250 * 380 * 2 / 1000 = 190.0 g
    assert pytest.approx(o2_feeding, abs=0.1) == 190.0


def test_feeding_event_spike_and_alarms():
    """Verify state transition when feeding a 5 m3 Tilapia tank."""
    initial_state = FishTankState(
        tank_id="TANK_01",
        species=FishSpecies.NILE_TILAPIA,
        fish_count=500,
        avg_weight_grams=400.0,
        total_biomass_kg=200.0,
        water_volume_m3=5.0,
        water_temp_c=26.0,
        ph=7.2,
        dissolved_oxygen_mg_l=6.5,
        tan_mg_l=0.30,
        toxic_nh3_mg_l=0.003,
    )

    # Feed 3.0 kg
    new_state, event = FishBioenergeticsEngine.apply_feeding_event(
        state=initial_state,
        feed_kg=3.0,
        crude_protein_pct=32.0,
    )

    assert event.feed_amount_kg == 3.0
    assert event.tan_generated_grams > 0.0
    assert new_state.tan_mg_l > initial_state.tan_mg_l
    assert new_state.total_biomass_kg > initial_state.total_biomass_kg
    assert new_state.dissolved_oxygen_mg_l < initial_state.dissolved_oxygen_mg_l
