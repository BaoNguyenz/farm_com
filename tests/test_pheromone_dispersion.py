"""
Unit test suite for Atmospheric Pheromone Plume Dispersion & Mating Disruption Engine.
"""

from backend.core.pheromone_dispersion import (
    PHEROMONE_CATALOG,
    PasquillStabilityClass,
    PheromoneDispersionEngine,
    TargetPestSpecies,
)


def test_pasquill_stability_classification():
    """Verify atmospheric stability classification across day/night and wind regimes."""
    engine = PheromoneDispersionEngine()

    # Sunny calm afternoon -> Class A (very unstable)
    assert engine.classify_stability(1.2, 750.0) == PasquillStabilityClass.A_VERY_UNSTABLE
    # Calm night (peak moth flight) -> Class F (stable)
    assert engine.classify_stability(1.2, 0.0) == PasquillStabilityClass.F_STABLE
    # Windy -> Class D (neutral)
    assert engine.classify_stability(6.5, 0.0) == PasquillStabilityClass.D_NEUTRAL


def test_arrhenius_emission_rate_scaling():
    """Verify pheromone volatilization rate increases exponentially with ambient temperature."""
    engine = PheromoneDispersionEngine()
    profile = PHEROMONE_CATALOG[TargetPestSpecies.SPODOPTERA_LITURA]

    q_15 = engine.compute_emission_rate_ng_s(profile, 15.0)
    q_25 = engine.compute_emission_rate_ng_s(profile, 25.0)
    q_35 = engine.compute_emission_rate_ng_s(profile, 35.0)

    assert q_15 < q_25 < q_35
    # At 25°C, 180 ug/h = 50.0 ng/s
    assert abs(q_25 - 50.0) < 0.1


def test_gaussian_plume_downwind_and_crosswind_decay():
    """Verify concentration decays with downwind distance and crosswind offset."""
    engine = PheromoneDispersionEngine()

    c_10_center = engine.evaluate_concentration_ng_m3(
        10.0, 0.0, 0.8, 50.0, 2.0, PasquillStabilityClass.E_SLIGHTLY_STABLE
    )
    c_30_center = engine.evaluate_concentration_ng_m3(
        30.0, 0.0, 0.8, 50.0, 2.0, PasquillStabilityClass.E_SLIGHTLY_STABLE
    )
    c_10_off_axis = engine.evaluate_concentration_ng_m3(
        10.0, 5.0, 0.8, 50.0, 2.0, PasquillStabilityClass.E_SLIGHTLY_STABLE
    )

    assert c_10_center > c_30_center > 0.0
    assert c_10_center > c_10_off_axis


def test_upwind_concentration_is_zero():
    """Verify concentration upwind of the emitter (x <= 0) is strictly zero."""
    engine = PheromoneDispersionEngine()
    assert (
        engine.evaluate_concentration_ng_m3(
            -5.0, 0.0, 0.8, 50.0, 2.0, PasquillStabilityClass.D_NEUTRAL
        )
        == 0.0
    )


def test_stable_night_increases_attraction_range_vs_turbulent_day():
    """Verify calm nighttime stable boundary layer carries pheromone plume farther than turbulent midday."""
    engine = PheromoneDispersionEngine()

    night_plume = engine.simulate_plume(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        ambient_temp_c=24.0,
        wind_speed_m_s=1.5,
        solar_irradiance_w_m2=0.0,
    )
    day_plume = engine.simulate_plume(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        ambient_temp_c=24.0,
        wind_speed_m_s=1.5,
        solar_irradiance_w_m2=750.0,
    )

    assert night_plume.stability_class == PasquillStabilityClass.F_STABLE
    assert day_plume.stability_class == PasquillStabilityClass.A_VERY_UNSTABLE
    assert night_plume.effective_attraction_range_m > day_plume.effective_attraction_range_m


def test_plume_simulation_dispenser_density():
    """Verify mating disruption simulation outputs valid dispenser density per hectare."""
    engine = PheromoneDispersionEngine()
    res = engine.simulate_plume(
        species=TargetPestSpecies.TUTA_ABSOLUTA,
        ambient_temp_c=22.0,
        wind_speed_m_s=2.0,
        solar_irradiance_w_m2=0.0,
    )

    assert res.effective_attraction_range_m >= res.mating_disruption_radius_m
    assert 4 <= res.recommended_dispensers_per_ha <= 250
