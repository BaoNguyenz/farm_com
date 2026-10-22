"""
Digital Twin Tick Simulation Engine.
Synchronously advances time across the spatial plot grid, updates thermal
degree days (GDD), transitions crop phenology stages, and simulates soil drying.
"""

from typing import Dict, Any, List
import time
from backend.core.twin_state import FarmDigitalTwin
from backend.core.crop_phenology import PhenologyEngine
from backend.core.agronomy_models import calculate_fao56_et0


class DigitalTwinTickEngine:
    """
    Coordinates multi-variable biophysical progression for the farm digital twin.
    """
    def __init__(self, default_crop: str = "maize"):
        self.pheno_engine = PhenologyEngine(crop_name=default_crop)

    def advance_tick(
        self,
        farm: FarmDigitalTwin,
        elapsed_hours: float = 1.0,
        rain_mm: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Advances the farm simulation by elapsed_hours.
        Updates soil moisture, thermal time, phenology, and records biophysical state.
        """
        weather = farm.current_weather
        t_mean = weather.temp_c
        t_max = weather.temp_max
        t_min = weather.temp_min

        # 1. Calculate daily reference evapotranspiration (ET0)
        daily_et0 = calculate_fao56_et0(
            temp_c=t_mean,
            humidity_percent=weather.humidity_percent,
            wind_speed_2m_ms=weather.wind_speed_ms,
            solar_radiation_mj_m2_day=weather.solar_radiation_mj,
        )
        hourly_et0 = daily_et0 / 24.0

        # 2. Hourly thermal degree accumulation (GDD)
        daily_gdd = self.pheno_engine.compute_daily_gdd(t_max=t_max, t_min=t_min)
        hourly_gdd = daily_gdd / 24.0

        stage_transitions: List[Dict[str, str]] = []
        moisture_changes: List[float] = []

        for zone in farm.zones:
            # Advance thermal time
            zone.accumulated_gdd = round(zone.accumulated_gdd + (hourly_gdd * elapsed_hours), 2)

            # Update growth stage if threshold reached
            old_stage = zone.growth_stage
            new_stage = self._determine_growth_stage(zone.accumulated_gdd)
            if new_stage != old_stage:
                zone.growth_stage = new_stage
                stage_transitions.append({"zone_id": zone.id, "from": old_stage, "to": new_stage})

            # Calculate crop evapotranspiration loss ETc = ET0 * Kc
            kc = self._approximate_kc(zone.growth_stage)
            water_loss_mm = hourly_et0 * kc * elapsed_hours

            # Soil physics: 1mm water loss ~ 0.65% volumetric moisture drop
            pct_loss = water_loss_mm * 0.65
            pct_gain = rain_mm * 1.5

            # Gravity drainage when saturated (> 80%)
            drainage = max(0.0, (zone.soil_moisture_pct - 80.0) * 0.20 * elapsed_hours)

            new_moisture = zone.soil_moisture_pct - pct_loss - drainage + pct_gain
            zone.soil_moisture_pct = max(10.0, min(95.0, round(new_moisture, 1)))
            moisture_changes.append(zone.soil_moisture_pct)

            # Health classification
            if zone.soil_moisture_pct < 38.0:
                zone.health_status = "water_stressed"
            elif zone.soil_moisture_pct > 88.0:
                zone.health_status = "waterlogged_risk"
            elif zone.ndvi < 0.40:
                zone.health_status = "low_biomass"
            else:
                zone.health_status = "healthy"

        farm.last_sync_timestamp = time.time()

        return {
            "elapsed_hours": elapsed_hours,
            "hourly_et0_mm": round(hourly_et0, 3),
            "hourly_gdd": round(hourly_gdd, 3),
            "rain_mm": rain_mm,
            "stage_transitions": stage_transitions,
            "mean_moisture_after_tick": round(sum(moisture_changes) / max(1, len(moisture_changes)), 1),
            "stressed_zone_count": len(farm.get_stressed_zones()),
        }

    @staticmethod
    def _determine_growth_stage(accumulated_gdd: float) -> str:
        """Maps GDD progress to standard digital twin growth stages."""
        if accumulated_gdd < 100.0:
            return "seedling"
        elif accumulated_gdd < 450.0:
            return "vegetative"
        elif accumulated_gdd < 850.0:
            return "flowering"
        elif accumulated_gdd < 1350.0:
            return "fruiting"
        else:
            return "harvest_ready"

    @staticmethod
    def _approximate_kc(stage: str) -> float:
        """Returns baseline FAO-56 crop coefficient by growth phase."""
        kc_map = {
            "seedling": 0.35,
            "vegetative": 0.75,
            "flowering": 1.15,
            "fruiting": 1.05,
            "harvest_ready": 0.50,
        }
        return kc_map.get(stage.lower(), 0.80)
