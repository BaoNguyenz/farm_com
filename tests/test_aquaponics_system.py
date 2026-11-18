"""
Unit test suite for coupled aquaponic recirculating ecosystem coordinator and mass balance.
"""
import pytest

from backend.core.aquaponics_hydroponics import BaseChemical
from backend.core.aquaponics_system import (
    AquaponicEcosystemCoordinator,
    AquaponicLoopStatus,
)


def test_coordinator_initial_state():
    """Verify default facility geometry, water turnover time, and equilibrium status."""
    coord = AquaponicEcosystemCoordinator(flow_rate_m3_h=3.5)

    tot_vol = coord.get_total_water_volume_m3()
    # 5.0 (fish) + 1.5 (biofilter) + 12.0 (DWC) = 18.5 m3
    assert tot_vol == 18.5

    telemetry = coord.step_simulation_cycle(feed_input_kg=0.0, dt_hours=1.0)
    assert telemetry.system_id == "AQUAPONICS_FACILITY_01"
    assert telemetry.ecosystem_status == AquaponicLoopStatus.OPTIMAL_EQUILIBRIUM
    assert telemetry.system_health_score >= 90.0
    # Turnover time = 18.5 / 3.5 = ~5.3 hours
    assert pytest.approx(telemetry.water_turnover_hours, abs=0.1) == 5.3
    assert telemetry.total_fish_biomass_kg == 225.0
    assert telemetry.total_crop_heads == 1000


def test_simulation_cycle_step_with_feeding():
    """Verify feeding spike, biological oxidation, and plant nutrient delivery."""
    coord = AquaponicEcosystemCoordinator(flow_rate_m3_h=3.5)

    # Administer 0.8 kg single-meal feed
    telemetry = coord.step_simulation_cycle(
        feed_input_kg=0.8,
        par_umol_m2_s=450.0,
        supplementary_aeration=True,
        dt_hours=1.0,
    )

    # Biofilter should oxidize TAN and produce NO3
    assert telemetry.biofilter.tan_oxidation_rate_g_h > 0.0
    assert telemetry.biofilter.no2_oxidation_rate_g_h > 0.0
    # Fish tank DO should stay healthy with supplementary aeration
    assert telemetry.fish_tank.dissolved_oxygen_mg_l >= 5.0
    assert telemetry.fish_tank.toxic_nh3_mg_l < 0.05
    # Alkalinity consumed by nitrification
    assert telemetry.hydroponics.alkalinity_mg_l_caco3 < 85.0


def test_buffer_dosing_restores_alkalinity():
    """Verify chemical buffer dosing elevates plant bed alkalinity."""
    coord = AquaponicEcosystemCoordinator()
    coord.hydroponic_state.alkalinity_mg_l_caco3 = 45.0  # Depleted alkalinity

    rec = coord.dose_alkalinity_buffer(
        chemical=BaseChemical.POTASSIUM_BICARBONATE,
        target_alkalinity_mg_l=100.0,
    )

    assert rec.dose_grams > 0.0
    assert rec.potassium_or_calcium_added_grams > 0.0
    assert coord.hydroponic_state.alkalinity_mg_l_caco3 == 100.0


def test_hypoxia_and_ammonia_alarm_diagnosis():
    """Verify health score penalty and diagnostic alerts under water quality stress."""
    coord = AquaponicEcosystemCoordinator()

    # Artificially induce hypoxia and high ammonia
    coord.fish_state.dissolved_oxygen_mg_l = 2.5
    coord.fish_state.toxic_nh3_mg_l = 0.08  # > 0.05 mg/L

    telemetry = coord.step_simulation_cycle(feed_input_kg=0.0, supplementary_aeration=False, dt_hours=1.0)

    assert telemetry.system_health_score < 80.0
    assert telemetry.ecosystem_status in [
        AquaponicLoopStatus.AMMONIA_SPIKE,
        AquaponicLoopStatus.HYPOXIA_CRITICAL,
    ]
    assert len(telemetry.recommendations) > 0
