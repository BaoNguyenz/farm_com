"""
Unit tests for the Kalman Filter Data Assimilation Engine.
Validates state prediction, variance propagation, observation updates,
cloud penalty attenuation, and twin state synchronisation.
"""

from backend.core.assimilation import (
    NDVIKalmanFilter,
    KalmanAssimilationConfig,
    DataAssimilationEngine,
    NDVIState,
)
from backend.core.twin_state import create_default_farm


def test_kalman_filter_initialization():
    filt = NDVIKalmanFilter(initial_ndvi=0.68, initial_variance=0.005)
    state = filt.get_state()
    assert isinstance(state, NDVIState)
    assert state.ndvi == 0.68
    assert state.variance == 0.005
    assert state.standard_deviation > 0.0

    lower, upper = state.confidence_interval()
    assert lower < state.ndvi < upper
    assert lower >= 0.0
    assert upper <= 1.0


def test_kalman_filter_predict_growth_and_decay():
    # 1. Under healthy conditions (adequate moisture, moderate VPD), NDVI slightly increases
    filt_growth = NDVIKalmanFilter(initial_ndvi=0.65, initial_variance=0.002)
    prior_var = filt_growth.p
    state_after_growth = filt_growth.predict(delta_days=5.0, vpd_kpa=0.8, soil_moisture_pct=65.0)

    assert state_after_growth.ndvi >= 0.65
    assert filt_growth.p > prior_var  # Variance grows between observations without satellite passes

    # 2. Under drought conditions (low moisture, high VPD), NDVI decays
    filt_drought = NDVIKalmanFilter(initial_ndvi=0.75, initial_variance=0.002)
    state_after_drought = filt_drought.predict(delta_days=5.0, vpd_kpa=2.2, soil_moisture_pct=25.0)

    assert state_after_drought.ndvi < 0.75
    assert state_after_drought.variance > 0.002


def test_kalman_filter_update_convergence_and_uncertainty_reduction():
    filt = NDVIKalmanFilter(initial_ndvi=0.60, initial_variance=0.01)

    # Prior prediction grows variance
    filt.predict(delta_days=5.0, vpd_kpa=1.0, soil_moisture_pct=50.0)
    var_before_obs = filt.p

    # Satellite pass provides clear-sky measurement (cloud_cover=0%)
    state_post = filt.update(observed_ndvi=0.80, cloud_cover_pct=0.0)

    # Posterior variance must be strictly smaller than prior variance
    assert filt.p < var_before_obs
    # State estimate moves toward observation
    assert state_post.ndvi > 0.60


def test_kalman_filter_cloud_cover_uncertainty_penalty():
    # Clear sky pass vs heavy cloud pass with identical initial state and observation
    filt_clear = NDVIKalmanFilter(initial_ndvi=0.60, initial_variance=0.005)
    filt_cloudy = NDVIKalmanFilter(initial_ndvi=0.60, initial_variance=0.005)

    filt_clear.update(observed_ndvi=0.85, cloud_cover_pct=0.0)
    filt_cloudy.update(observed_ndvi=0.85, cloud_cover_pct=80.0)

    # Clear observation should give more weight to satellite reading
    assert filt_clear.x > filt_cloudy.x
    # Clear observation achieves lower uncertainty than cloudy pass
    assert filt_clear.p < filt_cloudy.p


def test_data_assimilation_engine_simulation_and_satellite_pass():
    farm = create_default_farm(width=2, height=2)
    engine = DataAssimilationEngine(KalmanAssimilationConfig())

    # Step simulation 24 hours under dry conditions
    for zone in farm.zones:
        zone.soil_moisture_pct = 30.0

    step_results = engine.step_simulation(farm, elapsed_hours=24.0)
    assert len(step_results) == 4
    for z in farm.zones:
        assert z.ndvi <= 0.72  # Starting NDVI in default farm is 0.72

    # Ingest multi-spectral satellite overpass
    obs_batch = [
        {"zone_id": "Z_0_0", "observed_ndvi": 0.78},
        {"zone_id": "Z_0_1", "observed_ndvi": 0.76},
    ]
    assimilated = engine.ingest_satellite_pass(farm, obs_batch, cloud_cover_pct=10.0)
    assert len(assimilated) == 2
    assert farm.get_zone("Z_0_0").ndvi > 0.71
    assert "ci_95" in assimilated[0]
