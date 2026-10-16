"""
Open-Meteo Weather Client
Retrieves hyper-local meteorological and solar radiation data asynchronously.
"""
import httpx
from typing import Optional
from backend.core.twin_state import WeatherTelemetry

class WeatherClient:
    def __init__(self, lat: float = 11.9404, lon: float = 108.4583):
        self.lat = lat
        self.lon = lon
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    async def fetch_current_weather(self) -> WeatherTelemetry:
        """
        Fetch real-time weather and radiation from Open-Meteo API.
        Falls back to realistic seasonal data if offline or network error.
        """
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "wind_speed_10m",
                "cloud_cover"
            ],
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "shortwave_radiation_sum"
            ],
            "timezone": "auto"
        }
        
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.get(self.base_url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    curr = data.get("current", {})
                    daily = data.get("daily", {})
                    
                    temp = curr.get("temperature_2m", 24.0)
                    t_max = daily.get("temperature_2m_max", [27.0])[0]
                    t_min = daily.get("temperature_2m_min", [16.0])[0]
                    # Convert shortwave radiation MJ/m2 if available
                    radiation = daily.get("shortwave_radiation_sum", [18.0])[0]
                    
                    return WeatherTelemetry(
                        temp_c=temp,
                        temp_max=t_max,
                        temp_min=t_min,
                        humidity_percent=curr.get("relative_humidity_2m", 68.0),
                        wind_speed_ms=curr.get("wind_speed_10m", 2.2),
                        solar_radiation_mj=radiation,
                        precipitation_mm=curr.get("precipitation", 0.0),
                        cloud_cover_pct=curr.get("cloud_cover", 20.0)
                    )
        except Exception as e:
            # Fallback to realistic mock values
            pass

        return WeatherTelemetry(
            temp_c=23.8,
            temp_max=27.5,
            temp_min=17.0,
            humidity_percent=66.0,
            wind_speed_ms=2.0,
            solar_radiation_mj=17.8,
            precipitation_mm=0.0,
            cloud_cover_pct=25.0
        )
