"""
IoT Sensor Telemetry Simulator
Simulates soil moisture dynamic decay, evapotranspiration loss, and irrigation recharge.
"""
import random
from backend.core.twin_state import FarmDigitalTwin

class SensorSimulator:
    def __init__(self, farm: FarmDigitalTwin):
        self.farm = farm

    def step_simulation(self, elapsed_hours: float = 1.0, rain_mm: float = 0.0):
        """
        Advances the soil and plant dynamics over time.
        """
        for zone in self.farm.zones:
            # 1. Natural drying from evaporation (~0.4% - 0.9% moisture loss per hour)
            moisture_loss = random.uniform(0.3, 0.7) * elapsed_hours
            
            # 2. Gain from precipitation
            moisture_gain = rain_mm * 1.2
            
            zone.soil_moisture_pct = max(10.0, min(95.0, round(zone.soil_moisture_pct - moisture_loss + moisture_gain, 1)))
            
            # Minor sensor noise
            zone.soil_temp_c = round(self.farm.current_weather.temp_c - random.uniform(1.0, 3.0), 1)
            
            # Update health status
            if zone.soil_moisture_pct < 40.0:
                zone.health_status = "water_stressed"
            elif zone.ndvi < 0.45:
                zone.health_status = "low_biomass"
            else:
                zone.health_status = "healthy"
