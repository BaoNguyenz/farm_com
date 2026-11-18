"""
Unit test suite for aquaponic crop nitrate uptake, Michaelis-Menten kinetics, and alkalinity buffering.
"""
import pytest

from backend.core.aquaponics_hydroponics import (
    AquaponicCropType,
    AquaponicHydroponicsEngine,
    BaseChemical,
    HydroponicBedState,
    HydroponicSubsystemType,
)


def test_crop_nitrate_uptake_michaelis_menten():
    """Verify Michaelis-Menten nitrate consumption curves for lettuce."""
    plant_count = 1000

    # Low nitrate concentration (10 mg/L)
    uptake_low = AquaponicHydroponicsEngine.calculate_crop_nitrate_uptake(
        crop_type=AquaponicCropType.BUTTERHEAD_LETTUCE,
        plant_count=plant_count,
        no3_concentration_mg_l=10.0,
        par_umol_m2_s=400.0,
    )

    # High nitrate concentration (120 mg/L)
    uptake_high = AquaponicHydroponicsEngine.calculate_crop_nitrate_uptake(
        crop_type=AquaponicCropType.BUTTERHEAD_LETTUCE,
        plant_count=plant_count,
        no3_concentration_mg_l=120.0,
        par_umol_m2_s=400.0,
    )

    assert uptake_low < uptake_high
    # 1000 plants * 0.035 g = 35.0 g max; at high nitrate and 400 PAR, should be ~25-32 g
    assert 20.0 < uptake_high < 35.0


def test_buffer_dosing_khco3():
    """Verify potassium bicarbonate dosing for alkalinity restoration."""
    # Deficit: 100 - 60 = 40 mg/L in 10 m3 water = 400 g CaCO3 equiv deficit
    # KHCO3 ratio: 400 / 0.50 = 800 g KHCO3
    # Potassium added: 800 * 0.39 = 312 g K+
    rec = AquaponicHydroponicsEngine.calculate_buffer_dosing(
        current_alkalinity_mg_l=60.0,
        water_volume_m3=10.0,
        target_alkalinity_mg_l=100.0,
        chemical=BaseChemical.POTASSIUM_BICARBONATE,
    )

    assert rec.chemical == BaseChemical.POTASSIUM_BICARBONATE
    assert pytest.approx(rec.dose_grams, abs=0.5) == 800.0
    assert pytest.approx(rec.potassium_or_calcium_added_grams, abs=0.5) == 312.0
    assert "Potassium (K+)" in rec.rationale


def test_buffer_dosing_calcium_hydroxide():
    """Verify calcium hydroxide (hydrated lime) dosing."""
    # Deficit: 100 - 60 = 40 mg/L in 10 m3 = 400 g CaCO3 equiv
    # Ca(OH)2 ratio: 400 / 1.35 = 296.3 g Ca(OH)2
    rec = AquaponicHydroponicsEngine.calculate_buffer_dosing(
        current_alkalinity_mg_l=60.0,
        water_volume_m3=10.0,
        target_alkalinity_mg_l=100.0,
        chemical=BaseChemical.CALCIUM_HYDROXIDE,
    )

    assert rec.chemical == BaseChemical.CALCIUM_HYDROXIDE
    assert pytest.approx(rec.dose_grams, abs=1.0) == 296.3
    assert pytest.approx(rec.potassium_or_calcium_added_grams, abs=1.0) == 160.0
    assert "Calcium (Ca2+)" in rec.rationale


def test_zero_deficit_buffer_dosing():
    """Verify zero dosing when alkalinity already satisfies target."""
    rec = AquaponicHydroponicsEngine.calculate_buffer_dosing(
        current_alkalinity_mg_l=120.0,
        water_volume_m3=10.0,
        target_alkalinity_mg_l=100.0,
    )
    assert rec.dose_grams == 0.0
    assert rec.potassium_or_calcium_added_grams == 0.0


def test_simulate_hydroponic_step():
    """Verify single step of nitrate assimilation in DWC bed."""
    initial_bed = HydroponicBedState(
        bed_id="DWC_01",
        subsystem_type=HydroponicSubsystemType.DEEP_WATER_CULTURE_DWC,
        crop_type=AquaponicCropType.BUTTERHEAD_LETTUCE,
        bed_area_m2=40.0,
        plant_count=1000,
        water_volume_m3=12.0,
        inlet_no3_mg_l=85.0,
        outlet_no3_mg_l=85.0,
        daily_no3_uptake_grams=25.0,
        alkalinity_mg_l_caco3=75.0,
        ph=6.8,
    )

    next_bed = AquaponicHydroponicsEngine.simulate_hydroponic_step(
        state=initial_bed,
        inlet_no3_mg_l=85.0,
        water_flow_m3_h=3.5,
        par_umol_m2_s=450.0,
        dt_hours=1.0,
    )

    assert next_bed.outlet_no3_mg_l < next_bed.inlet_no3_mg_l
    assert next_bed.daily_no3_uptake_grams > 0.0
    assert next_bed.is_nitrate_deficient is False
