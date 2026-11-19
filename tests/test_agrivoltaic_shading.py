"""
Unit test suite for agrivoltaic dynamic canopy shading, photoinhibition mitigation, and PAR optimization.
"""
from backend.core.agrivoltaic_shading import (
    AgrivoltaicOperationalMode,
    AgrivoltaicShadingEngine,
)
from backend.core.agrivoltaic_tracking import (
    AgrivoltaicTrackerConfig,
    AgrivoltaicTrackingEngine,
)


def test_canopy_par_transmission_flat_vs_steep_tilt():
    """Verify that flat panel orientation casts wider shadows and reduces under-canopy PAR."""
    ambient_ghi = 800.0  # ~1640 umol/m2s PAR

    # Case A: Flat panels (tilt = 0.0°) -> maximum defensive shade
    micro_flat = AgrivoltaicShadingEngine.calculate_canopy_par_transmission(
        ambient_ghi_w_m2=ambient_ghi,
        panel_tilt_deg=0.0,
        zenith_deg=20.0,
    )

    # Case B: Steep tilted panels (tilt = 55.0°) -> open gaps for light transmission
    micro_steep = AgrivoltaicShadingEngine.calculate_canopy_par_transmission(
        ambient_ghi_w_m2=ambient_ghi,
        panel_tilt_deg=55.0,
        zenith_deg=20.0,
    )

    # Flat panel should have higher shading percentage
    assert micro_flat.shading_fraction_pct > micro_steep.shading_fraction_pct
    # Canopy PAR under flat panel should be lower than under steep panel
    assert micro_flat.canopy_par_umol_m2_s < micro_steep.canopy_par_umol_m2_s
    # Leaf temperature reduction is higher under flat shade
    assert micro_flat.leaf_temp_reduction_c > micro_steep.leaf_temp_reduction_c
    assert micro_flat.transpiration_reduction_pct > micro_steep.transpiration_reduction_pct


def test_zero_irradiance_night_canopy_par():
    """Verify microclimate behavior under zero nighttime irradiance."""
    micro_night = AgrivoltaicShadingEngine.calculate_canopy_par_transmission(
        ambient_ghi_w_m2=0.0,
        panel_tilt_deg=0.0,
        zenith_deg=120.0,
    )

    assert micro_night.ambient_par_umol_m2_s == 0.0
    assert micro_night.canopy_par_umol_m2_s == 0.0
    assert micro_night.shading_fraction_pct == 0.0
    assert micro_night.photoinhibition_risk == "none_night"


def test_evaluate_crop_protection_need_strawberry_burn():
    """Verify detection of critical thermal and radiant scald risks on strawberries."""
    # Under noon heatwave in Dalat: 33.0C leaf temp, 1600 PAR
    needed, reason = AgrivoltaicShadingEngine.evaluate_crop_protection_need(
        crop_type="Strawberries",
        canopy_temp_c=33.0,
        ambient_par=1650.0,
    )
    assert needed is True
    assert "photoinhibition" in reason.lower()

    # Under mild comfortable conditions: 23.0C leaf temp, 800 PAR
    safe_needed, safe_reason = AgrivoltaicShadingEngine.evaluate_crop_protection_need(
        crop_type="Strawberries",
        canopy_temp_c=23.0,
        ambient_par=800.0,
    )
    assert safe_needed is False
    assert "normal" in safe_reason.lower()


def test_resolve_agrivoltaic_dispatch_triggers_crop_defense_shading():
    """Verify dispatch arbiter commands flat 0° tilt when crops experience heat stress."""
    config = AgrivoltaicTrackerConfig()
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=120, local_hour=12.5)

    decision = AgrivoltaicShadingEngine.resolve_agrivoltaic_dispatch(
        solar_pos=pos,
        config=config,
        ambient_ghi_w_m2=920.0,  # ~1880 PAR
        canopy_temp_c=33.5,     # > 30.5C heat stress
        crop_type="Strawberries",
    )

    assert decision.active_mode == AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING
    assert decision.commanded_tilt_deg == 0.0
    assert decision.crop_stress_mitigated is True
    assert "CROP DEFENSE SHADING ENGAGED" in decision.rationale
    assert decision.canopy_microclimate.leaf_temp_reduction_c >= 1.5


def test_resolve_agrivoltaic_dispatch_max_power_under_mild_conditions():
    """Verify dispatch arbiter tracks sun for maximum clean electricity under mild crop conditions."""
    config = AgrivoltaicTrackerConfig()
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=120, local_hour=10.0)

    decision = AgrivoltaicShadingEngine.resolve_agrivoltaic_dispatch(
        solar_pos=pos,
        config=config,
        ambient_ghi_w_m2=500.0,  # ~1025 PAR
        canopy_temp_c=24.0,     # Mild
        crop_type="Strawberries",
    )

    assert decision.active_mode == AgrivoltaicOperationalMode.MAX_ELECTRICITY_YIELD
    assert decision.crop_stress_mitigated is False
    assert "MAX POWER TRACKING" in decision.rationale
    assert decision.tracker_state.generated_power_kw > 0.0


def test_sunlight_priority_low_diffuse_light():
    """Verify dispatch arbiter tilts steep to open row gaps under low diffuse light."""
    config = AgrivoltaicTrackerConfig()
    pos = AgrivoltaicTrackingEngine.calculate_solar_position(day_of_year=120, local_hour=7.5)

    decision = AgrivoltaicShadingEngine.resolve_agrivoltaic_dispatch(
        solar_pos=pos,
        config=config,
        ambient_ghi_w_m2=150.0,  # ~300 PAR (low diffuse morning light)
        canopy_temp_c=19.0,
        crop_type="Strawberries",
    )

    assert decision.active_mode == AgrivoltaicOperationalMode.CROP_SUNLIGHT_PRIORITY
    assert decision.commanded_tilt_deg == 50.0
    assert "SUNLIGHT PRIORITY" in decision.rationale
