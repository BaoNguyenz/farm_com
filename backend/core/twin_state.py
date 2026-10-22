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

    def get_zone_at(self, x: int, y: int) -> Optional[PlotZone]:
        """Lookup zone by coordinate (x, y)."""
        for zone in self.zones:
            if zone.x == x and zone.y == y:
                return zone
        return None

    def get_neighbors(self, x: int, y: int, diagonal: bool = False) -> List[PlotZone]:
        """
        Retrieves adjacent plot zones for microclimate & pest spread modeling.
        Von Neumann neighborhood (4-way) or Moore neighborhood (8-way if diagonal=True).
        """
        deltas = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        if diagonal:
            deltas.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])

        neighbors = []
        for dx, dy in deltas:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.grid_width and 0 <= ny < self.grid_height:
                zone = self.get_zone_at(nx, ny)
                if zone:
                    neighbors.append(zone)
        return neighbors

    def get_stressed_zones(self) -> List[PlotZone]:
        """Returns all plot zones currently exhibiting moisture or canopy stress."""
        return [
            z for z in self.zones
            if z.health_status in ("water_stressed", "low_biomass", "chlorosis", "waterlogged_risk")
            or z.soil_moisture_pct < 40.0
            or z.ndvi < 0.45
        ]

    def get_zones_by_crop(self, crop_type: str) -> List[PlotZone]:
        """Filters plot zones by specific crop species."""
        target = crop_type.lower().strip()
        return [z for z in self.zones if target in z.crop_type.lower()]

    def get_spatial_summary(self) -> Dict[str, Any]:
        """Calculates aggregated macro-indicators across the entire digital twin grid."""
        if not self.zones:
            return {}

        total = len(self.zones)
        mean_moisture = sum(z.soil_moisture_pct for z in self.zones) / total
        mean_ndvi = sum(z.ndvi for z in self.zones) / total
        mean_ndwi = sum(z.ndwi for z in self.zones) / total
        stressed = self.get_stressed_zones()

        return {
            "total_zones": total,
            "grid_dimensions": f"{self.grid_width}x{self.grid_height}",
            "mean_soil_moisture_pct": round(mean_moisture, 1),
            "mean_ndvi": round(mean_ndvi, 3),
            "mean_ndwi": round(mean_ndwi, 3),
            "stressed_zone_count": len(stressed),
            "healthy_zone_count": total - len(stressed),
        }

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
