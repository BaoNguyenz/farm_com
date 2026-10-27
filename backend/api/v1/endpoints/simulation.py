"""
Simulation Controller & Environmental Injection Endpoints (v1)
Enables stepping simulation time, injecting weather anomalies, and resetting twin state.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any
from backend.core.twin_state import FarmDigitalTwin, WeatherSnapshot, create_default_farm


router = APIRouter(prefix="/simulation", tags=["Simulation Engine v1"])


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


class SimulationTickRequest(BaseModel):
    hours: float = Field(1.0, ge=0.1, le=168.0, description="Hours of time to advance")
    rain_mm: float = Field(0.0, ge=0.0, description="Rainfall depth in millimeters")


class WeatherInjectionRequest(BaseModel):
    temp_c: float = Field(..., ge=-10.0, le=55.0, description="Ambient air temperature in Celsius")
    humidity_percent: float = Field(..., ge=5.0, le=100.0, description="Relative humidity percentage")
    solar_radiation_mj: float = Field(15.0, ge=0.0, le=45.0, description="Daily solar radiation MJ/m2")
    wind_speed_ms: float = Field(1.5, ge=0.0, le=35.0, description="Wind speed at 2m in m/s")
    precipitation_mm: float = Field(0.0, ge=0.0, description="Rainfall depth in mm")


@router.post("/tick")
async def step_simulation(
    payload: SimulationTickRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Advance simulation time, apply physics models, and step plant phenology."""
    from backend.main import sensor_sim, weather_client

    # 1. Update weather if real client is active, otherwise step synthetic
    try:
        live_w = await weather_client.fetch_current_weather()
        farm.current_weather = live_w
    except Exception:
        pass

    if payload.rain_mm > 0.0:
        farm.current_weather.precipitation_mm = payload.rain_mm

    # 2. Advance physics via sensor simulator
    sensor_sim.step_simulation(elapsed_hours=payload.hours, rain_mm=payload.rain_mm)

    return {
        "status": "success",
        "action": "simulation_advanced",
        "elapsed_hours": payload.hours,
        "rain_mm": payload.rain_mm,
        "total_zones": len(farm.zones),
        "current_weather": farm.current_weather.model_dump()
    }


@router.post("/weather")
async def inject_weather(
    payload: WeatherInjectionRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Inject custom microclimate weather scenario (e.g. drought or high-humidity fungal risk)."""
    injected = WeatherSnapshot(
        temp_c=payload.temp_c,
        humidity_percent=payload.humidity_percent,
        solar_radiation_mj=payload.solar_radiation_mj,
        wind_speed_ms=payload.wind_speed_ms,
        precipitation_mm=payload.precipitation_mm
    )
    farm.current_weather = injected

    return {
        "status": "success",
        "action": "weather_injected",
        "weather": injected.model_dump()
    }


@router.post("/reset")
async def reset_simulation(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Reset Digital Twin grid and plot zones back to pristine default state."""
    from backend.config import settings
    fresh_farm = create_default_farm(width=settings.grid_size_x, height=settings.grid_size_y)

    # Copy fresh attributes into singleton instance
    farm.zones = fresh_farm.zones
    farm.action_history = []
    farm.current_weather = fresh_farm.current_weather

    return {
        "status": "success",
        "action": "simulation_reset",
        "zones_reset_count": len(farm.zones)
    }
