"""
Unit tests for Canopy Heat Stress and Evaporative Fogging Controller.
Validates Vapor Pressure Deficit (VPD) kinetics, Steadman heat index,
severity classifications, and automated micro-fogging action dispatch.
"""

from backend.core.heat_stress import (
    CanopyHeatStressController,
    HeatStressAssessment,
)


def test_vpd_calculation():
    # Humid morning: 22°C, 85% RH -> low atmospheric drying demand
    vpd_humid = CanopyHeatStressController.calculate_vpd(22.0, 85.0)
    assert 0.3 <= vpd_humid <= 0.6

    # Scorching dry afternoon: 36°C, 25% RH -> severe vapor deficit
    vpd_arid = CanopyHeatStressController.calculate_vpd(36.0, 25.0)
    assert vpd_arid >= 4.0


def test_thermal_stress_evaluation_normal():
    assessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=24.0,
        humidity_percent=65.0
    )
    assert isinstance(assessment, HeatStressAssessment)
    assert assessment.alert_level == "normal"
    assert assessment.fogging_required is False
    assert assessment.pulse_duration_seconds == 0


def test_thermal_stress_evaluation_severe():
    # 33°C, 45% RH -> high VPD (~2.8 kPa)
    assessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=33.0,
        humidity_percent=45.0
    )
    assert assessment.alert_level in ("severe_heat_stress", "extreme_thermal_shock")
    assert assessment.fogging_required is True
    assert assessment.pulse_duration_seconds in (60, 120)
    assert assessment.water_liters_per_zone > 0.0


def test_thermal_stress_evaluation_extreme():
    assessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=38.5,
        humidity_percent=28.0
    )
    assert assessment.alert_level == "extreme_thermal_shock"
    assert assessment.fogging_required is True
    assert assessment.pulse_duration_seconds == 120
    assert assessment.water_liters_per_zone == 8.5
    assert "CRITICAL HEAT SHOCK" in assessment.action_summary


def test_misting_action_dispatch():
    assessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=36.0,
        humidity_percent=35.0
    )
    zones = ["Z_0_0", "Z_0_1", "Z_1_0", "Z_1_1"]

    action = CanopyHeatStressController.dispatch_misting_action(
        assessment=assessment,
        zone_ids=zones,
        water_available=True
    )

    assert action["action"] == "activate_evaporative_fogging"
    assert action["fogging_active"] is True
    assert len(action["target_zones"]) == 4
    assert action["total_water_liters"] == round(assessment.water_liters_per_zone * 4, 1)
    assert action["expected_temp_reduction_c"] == 3.5


def test_misting_action_when_water_unavailable():
    assessment = CanopyHeatStressController.evaluate_thermal_stress(
        air_temp_c=37.0,
        humidity_percent=30.0
    )
    action = CanopyHeatStressController.dispatch_misting_action(
        assessment=assessment,
        zone_ids=["Z_0_0"],
        water_available=False
    )

    assert action["action"] == "none"
    assert action["fogging_active"] is False
    assert "insufficient water reserve" in action["reason"]
