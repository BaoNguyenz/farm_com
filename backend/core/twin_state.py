"""
Digital Twin State Representations
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time

class PlotZone(BaseModel):
    id: str
    x: int
    y: int
    crop_type: str = "Strawberries"
    growth_stage: str = "flowering"  # seedling, vegetative, flowering, fruiting, harvest_ready
    accumulated_gdd: float = 340.0
    soil_moisture_pct: float = 62.5
    soil_ph: float = 6.2
    soil_temp_c: float = 21.0
    ndvi: float = 0.72
    ndwi: float = 0.35
    health_status: str = "healthy"
    last_irrigated_timestamp: float = Field(default_factory=time.time)

class WeatherTelemetry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    temp_c: float = 24.5
    temp_max: float = 28.0
    temp_min: float = 16.5
    humidity_percent: float = 65.0
    wind_speed_ms: float = 2.1
    solar_radiation_mj: float = 18.5
    precipitation_mm: float = 0.0
    cloud_cover_pct: float = 15.0

class ActionLog(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    agent_name: str
    action_type: str
    target_zone: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    rationale: str

class FarmDigitalTwin(BaseModel):
    farm_id: str = "farm-01"
    name: str = "Da Lat Smart Farm Beta"
    latitude: float = 11.9404
    longitude: float = 108.4583
    grid_width: int = 4
    grid_height: int = 4
    current_weather: WeatherTelemetry = Field(default_factory=WeatherTelemetry)
    zones: List[PlotZone] = Field(default_factory=list)
    action_history: List[ActionLog] = Field(default_factory=list)
    last_sync_timestamp: float = Field(default_factory=time.time)

    def get_zone(self, zone_id: str) -> Optional[PlotZone]:
        for zone in self.zones:
            if zone.id == zone_id:
                return zone
        return None

def create_default_farm(width: int = 4, height: int = 4) -> FarmDigitalTwin:
    """Factory to create an initialized farm grid with distinct zones."""
    crops = ["Strawberries", "Bell Pepper", "Arabica Coffee", "Hydrangea"]
    zones = []
    
    for y in range(height):
        for x in range(width):
            crop = crops[(x + y) % len(crops)]
            zone_id = f"Z_{x}_{y}"
            
            # Slightly vary initial properties
            moisture = 55.0 + ((x * 7 + y * 13) % 25)
            ndvi_val = 0.60 + ((x * 3 + y * 5) % 30) / 100.0
            ndwi_val = 0.20 + ((x + y * 2) % 25) / 100.0
            
            # Simulate one stressed zone for demonstration
            if x == 2 and y == 1:
                moisture = 38.0
                ndvi_val = 0.41
                ndwi_val = 0.08
                status = "water_stressed"
            else:
                status = "healthy"
                
            zones.append(PlotZone(
                id=zone_id,
                x=x,
                y=y,
                crop_type=crop,
                growth_stage="flowering" if x % 2 == 0 else "vegetative",
                soil_moisture_pct=round(moisture, 1),
                ndvi=round(ndvi_val, 2),
                ndwi=round(ndwi_val, 2),
                health_status=status
            ))
            
    return FarmDigitalTwin(
        grid_width=width,
        grid_height=height,
        zones=zones
    )
