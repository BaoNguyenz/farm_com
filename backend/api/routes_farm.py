"""
Farm State & Telemetry Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from backend.core.twin_state import FarmDigitalTwin, PlotZone

router = APIRouter(prefix="/api/farm", tags=["Farm Digital Twin"])

# Shared state dependency will be injected from main.py
def get_farm_instance():
    from backend.main import farm_instance
    return farm_instance

@router.get("/state")
async def get_farm_state(farm: FarmDigitalTwin = Depends(get_farm_instance)) -> Dict[str, Any]:
    """Retrieve full digital twin representation including all zones and weather."""
    return farm.model_dump()

@router.get("/zones/{zone_id}")
async def get_zone(zone_id: str, farm: FarmDigitalTwin = Depends(get_farm_instance)) -> PlotZone:
    """Retrieve fine-grained diagnostics for an individual plot zone."""
    zone = farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found.")
    return zone

@router.post("/tick")
async def advance_simulation(hours: float = 1.0, rain_mm: float = 0.0, farm: FarmDigitalTwin = Depends(get_farm_instance)):
    """Simulate passage of time, soil evaporation, and weather update."""
    from backend.main import sensor_sim, weather_client
    
    # 1. Update weather
    farm.current_weather = await weather_client.fetch_current_weather()
    # 2. Step physics
    sensor_sim.step_simulation(elapsed_hours=hours, rain_mm=rain_mm)
    
    return {
        "status": "simulation_stepped",
        "elapsed_hours": hours,
        "current_weather": farm.current_weather
    }
