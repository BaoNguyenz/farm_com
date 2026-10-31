"""
Data Assimilation Engine for Satellite Remote Sensing and Digital Twin Synchronisation.

Implements a 1D Kalman Filter to assimilate sparse, periodic satellite observations
(e.g., Sentinel-2 5-day revisit cycle) with continuous ground-truth microclimate telemetry
(soil moisture, Vapor Pressure Deficit / VPD, canopy temperature).
"""

from typing import Dict, Any, Optional, Tuple, List
import math
import time
from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin, PlotZone


class NDVIState(BaseModel):
    """Estimated state vector and uncertainty bounds for vegetation index."""
    ndvi: float = Field(..., description="Estimated canopy NDVI [0.0 - 1.0]")
    variance: float = Field(..., description="Estimated estimation error variance P_k")
    timestamp: float = Field(default_factory=time.time, description="Epoch timestamp of estimate")

    @property
    def standard_deviation(self) -> float:
        return math.sqrt(max(self.variance, 1e-8))

    def confidence_interval(self, z_score: float = 1.96) -> Tuple[float, float]:
        """Returns 95% (or custom z-score) confidence interval (lower, upper)."""
        sigma = self.standard_deviation
        return (
            max(0.0, round(self.ndvi - z_score * sigma, 4)),
            min(1.0, round(self.ndvi + z_score * sigma, 4))
        )


class KalmanAssimilationConfig(BaseModel):
    """Hyperparameters and noise covariances for satellite data assimilation."""
    process_noise_q: float = Field(0.0004, description="Process model uncertainty growth variance per day")
    measurement_noise_r: float = Field(0.0016, description="Sentinel-2 BOA surface reflectance variance (sigma=0.04)")
    cloud_penalty_factor: float = Field(0.05, description="Measurement noise multiplier per cloud cover %")
    vpd_stress_decay: float = Field(0.0035, description="Max daily NDVI decay under severe water deficit and atmospheric drying")
    optimal_growth_rate: float = Field(0.0020, description="Daily NDVI expansion rate under optimal moisture conditions")
    min_ndvi: float = 0.05
    max_ndvi: float = 0.95


class NDVIKalmanFilter:
    """
    Kalman filter tracking canopy NDVI between satellite passes.

    State transition model:
      x_k = x_{k-1} + f(VPD, SoilMoisture) * dt + w_k,  w_k ~ N(0, Q * dt)
    Observation model:
      z_k = x_k + v_k,  v_k ~ N(0, R)
    """

    def __init__(
        self,
        initial_ndvi: float = 0.70,
        initial_variance: float = 0.005,
        config: Optional[KalmanAssimilationConfig] = None
    ) -> None:
        self.config = config or KalmanAssimilationConfig()
        self.x: float = max(self.config.min_ndvi, min(self.config.max_ndvi, initial_ndvi))
        self.p: float = max(initial_variance, 1e-6)
        self.last_update_ts: float = time.time()

    def predict(
        self,
        delta_days: float,
        vpd_kpa: float = 1.0,
        soil_moisture_pct: float = 60.0
    ) -> NDVIState:
        """
        Projects state and error covariance forward by delta_days according to
        crop phenology and environmental drying stressors.
        """
        if delta_days <= 0.0:
            return self.get_state()

        # Dynamic process model f(u):
        # Under water stress (< 45% moisture) & high VPD (> 1.2 kPa), canopy transpires under stress, leading to senescence
        rate = 0.0
        if soil_moisture_pct < 45.0:
            stress_intensity = min(1.0, (45.0 - soil_moisture_pct) / 25.0)
            vpd_factor = max(0.5, min(2.0, vpd_kpa / 1.0))
            rate = -1.0 * self.config.vpd_stress_decay * stress_intensity * vpd_factor
        elif soil_moisture_pct >= 55.0 and self.x < self.config.max_ndvi:
            # Positive vegetative expansion
            rate = self.config.optimal_growth_rate * min(1.0, (soil_moisture_pct - 50.0) / 20.0)

        # State projection
        self.x = max(self.config.min_ndvi, min(self.config.max_ndvi, self.x + rate * delta_days))

        # Covariance projection: P_{k|k-1} = P_{k-1} + Q * dt
        self.p = self.p + self.config.process_noise_q * delta_days
        self.last_update_ts += delta_days * 86400.0

        return self.get_state()

    def update(
        self,
        observed_ndvi: float,
        measurement_variance: Optional[float] = None,
        cloud_cover_pct: float = 0.0
    ) -> NDVIState:
        """
        Assimilates a remote sensing observation z_k with observation covariance R.
        Inflates R if clouds or atmospheric aerosol contamination are present.
        """
        # Determine effective observation covariance R
        base_r = measurement_variance if measurement_variance is not None else self.config.measurement_noise_r
        effective_r = base_r * (1.0 + max(0.0, cloud_cover_pct) * self.config.cloud_penalty_factor)

        # Innovation (measurement residual) y_k = z_k - H * x_k (H = 1)
        z = max(self.config.min_ndvi, min(self.config.max_ndvi, observed_ndvi))
        y = z - self.x

        # Innovation covariance S_k = H * P * H^T + R = P + R
        s = self.p + effective_r

        # Kalman gain K_k = P * H^T / S = P / S
        k = self.p / s

        # State posterior update x_{k|k} = x_{k|k-1} + K * y
        self.x = max(self.config.min_ndvi, min(self.config.max_ndvi, self.x + k * y))

        # Covariance posterior update P_{k|k} = (1 - K) * P_{k|k-1}
        self.p = max(1e-6, (1.0 - k) * self.p)

        return self.get_state()

    def get_state(self) -> NDVIState:
        return NDVIState(
            ndvi=round(self.x, 4),
            variance=round(self.p, 6),
            timestamp=self.last_update_ts
        )


class DataAssimilationEngine:
    """
    Central farm data assimilation manager coordinating state tracking across all zones.
    Bridges Sentinel-2 revisit cadence (5-day intervals) with real-time digital twin state.
    """

    def __init__(self, config: Optional[KalmanAssimilationConfig] = None) -> None:
        self.config = config or KalmanAssimilationConfig()
        self.zone_filters: Dict[str, NDVIKalmanFilter] = {}

    def get_or_create_filter(self, zone_id: str, current_ndvi: float = 0.70) -> NDVIKalmanFilter:
        if zone_id not in self.zone_filters:
            self.zone_filters[zone_id] = NDVIKalmanFilter(
                initial_ndvi=current_ndvi,
                initial_variance=0.004,
                config=self.config
            )
        return self.zone_filters[zone_id]

    def step_simulation(self, farm: FarmDigitalTwin, elapsed_hours: float) -> Dict[str, NDVIState]:
        """
        Advances the physical process model for each zone based on microclimate telemetry.
        """
        results: Dict[str, NDVIState] = {}
        delta_days = elapsed_hours / 24.0

        # Calculate VPD from weather snapshot
        temp = farm.current_weather.temp_c
        rh = farm.current_weather.humidity_percent
        # Tetens formula for saturation vapor pressure
        es = 0.61078 * math.exp((17.27 * temp) / (temp + 237.3))
        ea = es * (rh / 100.0)
        vpd = max(0.05, es - ea)

        for zone in farm.zones:
            filt = self.get_or_create_filter(zone.id, current_ndvi=zone.ndvi)
            state = filt.predict(
                delta_days=delta_days,
                vpd_kpa=vpd,
                soil_moisture_pct=zone.soil_moisture_pct
            )
            zone.ndvi = state.ndvi
            results[zone.id] = state

        return results

    def ingest_satellite_pass(
        self,
        farm: FarmDigitalTwin,
        observations: List[Dict[str, Any]],
        cloud_cover_pct: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Assimilates a multi-spectral satellite overpass across observed zones.
        Each observation dict must include 'zone_id' and 'observed_ndvi'.
        """
        assimilated: List[Dict[str, Any]] = []

        for obs in observations:
            z_id = obs["zone_id"]
            z_val = float(obs["observed_ndvi"])
            filt = self.get_or_create_filter(z_id)
            state = filt.update(observed_ndvi=z_val, cloud_cover_pct=cloud_cover_pct)

            # Synchronize zone digital twin
            zone: Optional[PlotZone] = farm.get_zone(z_id)
            if zone:
                zone.ndvi = state.ndvi

            ci = state.confidence_interval()
            assimilated.append({
                "zone_id": z_id,
                "assimilated_ndvi": state.ndvi,
                "uncertainty_sigma": round(state.standard_deviation, 4),
                "ci_95": ci,
                "raw_observation": z_val
            })

        return assimilated
