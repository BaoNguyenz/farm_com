"""
IoT Sensor Telemetry Simulator
Simulates soil moisture dynamic decay, diurnal drying cycles,
gravity drainage, and targeted irrigation recharge events.
"""
import random
import math
from typing import Dict, Any
from backend.core.twin_state import FarmDigitalTwin


class SensorSimulator:
    """
    Simulates agricultural soil physics: diurnal solar evaporation,
    saturation drainage, soil thermal inertia, and irrigation replenishment.
    """
    def __init__(self, farm: FarmDigitalTwin):
        self.farm = farm
        self.simulation_hour: float = 8.0  # Starts at 08:00 morning

    def step_simulation(self, elapsed_hours: float = 1.0, rain_mm: float = 0.0):
        """
        Advances the soil and plant biophysical state over elapsed time.
        """
        self.simulation_hour = (self.simulation_hour + elapsed_hours) % 24.0
        is_daytime = 6.0 <= self.simulation_hour <= 18.0

        # Day drying rate is significantly higher due to solar radiation and vapor deficit
        base_rate = random.uniform(0.5, 0.9) if is_daytime else random.uniform(0.1, 0.3)
        moisture_loss_hourly = base_rate * elapsed_hours

        for zone in self.farm.zones:
            # 1. Drainage physics: above field capacity (80%), water drains rapidly downward
            gravity_drainage = 0.0
            if zone.soil_moisture_pct > 80.0:
                gravity_drainage = (zone.soil_moisture_pct - 80.0) * 0.25 * elapsed_hours

            # 2. Gain from rainfall (1mm rain ~ 1.5% volumetric soil moisture recharge)
            moisture_gain = rain_mm * 1.5

            net_moisture = zone.soil_moisture_pct - moisture_loss_hourly - gravity_drainage + moisture_gain
            zone.soil_moisture_pct = max(10.0, min(95.0, round(net_moisture, 1)))

            # 3. Soil thermal inertia: soil temperature lags air temperature by ~2°C
            air_temp = self.farm.current_weather.temp_c
            soil_thermal_offset = random.uniform(1.2, 2.5) if is_daytime else random.uniform(-0.5, 1.0)
            zone.soil_temp_c = round(air_temp - soil_thermal_offset, 1)

            # 4. Biomass and canopy health status classification
            if zone.soil_moisture_pct < 35.0:
                zone.health_status = "water_stressed"
            elif zone.ndvi < 0.40:
                zone.health_status = "low_biomass"
            elif zone.soil_moisture_pct > 88.0:
                zone.health_status = "waterlogged_risk"
            else:
                zone.health_status = "healthy"

    def apply_irrigation_recharge(self, zone_id: str, water_liters: float) -> Dict[str, Any]:
        """
        Applies a localized irrigation event to replenish root zone moisture.
        1000 Liters on a 25m2 plot ~ 40mm water depth ~ +20% soil moisture.
        """
        for zone in self.farm.zones:
            if zone.id == zone_id:
                moisture_bump = round(water_liters * 0.02, 1)
                zone.soil_moisture_pct = min(92.0, round(zone.soil_moisture_pct + moisture_bump, 1))
                if zone.soil_moisture_pct >= 40.0 and zone.health_status == "water_stressed":
                    zone.health_status = "healthy"
                return {
                    "zone_id": zone_id,
                    "applied_liters": water_liters,
                    "moisture_increase_pct": moisture_bump,
                    "current_moisture_pct": zone.soil_moisture_pct,
                    "status": zone.health_status
                }
        return {"error": f"Zone {zone_id} not found."}
