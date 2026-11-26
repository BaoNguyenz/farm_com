"""
Unit test suite for Dynamic LED Photobiology, DLI Controller & Phytochrome Spectrum Engine.
"""

from backend.core.led_photobiology import (
    LEDPhotobiologyEngine,
    PhotobiologyRecipe,
)


def test_dli_accumulation_formula():
    """Verify DLI = PPFD * hours * 0.0036 conversion."""
    engine = LEDPhotobiologyEngine()
    # 500 umol/m2/s for 10 hours = 18.0 mol/m2/day
    assert engine.compute_dli(500.0, 10.0) == 18.0


def test_phytochrome_pss_and_shade_avoidance():
    """Verify high Far-Red lowers R:FR ratio and triggers shade-avoidance risk."""
    engine = LEDPhotobiologyEngine()

    compact = engine.tune_supplemental_lighting(recipe=PhotobiologyRecipe.VEGETATIVE_COMPACT)
    assert compact.r_fr_ratio > 10.0
    assert compact.phytochrome_pss > 0.80
    assert compact.shade_avoidance_risk is False

    # Excess Far-Red (35%) triggers shade-avoidance stretching
    stretched = engine.tune_supplemental_lighting(
        recipe=PhotobiologyRecipe.FRUIT_ELONGATION,
        custom_far_red_pct=35.0,
    )
    assert stretched.r_fr_ratio < 3.0
    assert stretched.shade_avoidance_risk is True


def test_supplemental_dli_deficit_and_power():
    """Verify supplemental PPFD and LED electrical power density calculation."""
    engine = LEDPhotobiologyEngine()
    res = engine.tune_supplemental_lighting(
        recipe=PhotobiologyRecipe.FLOWERING_ANTHOCYANIN,
        target_dli_mol_m2_day=18.0,
        solar_dli_mol_m2_day=10.8,
        photoperiod_hours=10.0,
    )

    assert res.supplemental_dli_needed == 7.2
    # 7.2 / (10 * 0.0036) = 200.0 umol/m2/s
    assert res.supplemental_ppfd_umol_m2_s == 200.0
    assert res.fixture_power_w_per_m2 > 60.0
    assert res.energy_kwh_per_m2_day > 0.6


def test_zero_deficit_turns_off_leds():
    """Verify zero supplemental power when ambient solar DLI meets target."""
    engine = LEDPhotobiologyEngine()
    res = engine.tune_supplemental_lighting(
        target_dli_mol_m2_day=16.0,
        solar_dli_mol_m2_day=19.5,
    )
    assert res.supplemental_dli_needed == 0.0
    assert res.supplemental_ppfd_umol_m2_s == 0.0
    assert res.fixture_power_w_per_m2 == 0.0
