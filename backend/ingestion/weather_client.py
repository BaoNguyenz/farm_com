"""
Open-Meteo Weather Client
Retrieves hyper-local meteorological and solar radiation data asynchronously.
"""
import asyncio
import time
import httpx
from typing import Optional
from backend.core.twin_state import WeatherTelemetry


class WeatherClient:
    """
    Asynchronous Open-Meteo weather client with local TTL caching,
    automatic retry logic, and resilient biophysical fallbacks.
    """
    def __init__(self, lat: float = 11.9404, lon: float = 108.4583, cache_ttl_seconds: int = 300):
        self.lat = lat
        self.lon = lon
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cached_telemetry: Optional[WeatherTelemetry] = None
        self._cache_timestamp: float = 0.0

    def is_cache_valid(self) -> bool:
        """Checks if current in-memory cached telemetry is within TTL."""
        return (
            self._cached_telemetry is not None
            and (time.time() - self._cache_timestamp) < self.cache_ttl_seconds
        )

    def clear_cache(self) -> None:
        """Invalidates local weather cache."""
        self._cached_telemetry = None
        self._cache_timestamp = 0.0

    async def fetch_current_weather(self, max_retries: int = 3) -> WeatherTelemetry:
        """
        Fetch real-time weather and radiation from Open-Meteo API.
        Uses in-memory cache if fresh, otherwise performs retries with backoff.
        Falls back to seasonal Highland benchmarks if network fails.
        """
        if self.is_cache_valid():
            return self._cached_telemetry

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

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.get(self.base_url, params=params)
                    if res.status_code == 200:
                        data = res.json()
                        curr = data.get("current", {})
                        daily = data.get("daily", {})

                        temp = curr.get("temperature_2m", 24.0)
                        t_max = daily.get("temperature_2m_max", [27.0])[0]
                        t_min = daily.get("temperature_2m_min", [16.0])[0]
                        radiation = daily.get("shortwave_radiation_sum", [18.0])[0]

                        telemetry = WeatherTelemetry(
                            temp_c=float(temp),
                            temp_max=float(t_max),
                            temp_min=float(t_min),
                            humidity_percent=float(curr.get("relative_humidity_2m", 68.0)),
                            wind_speed_ms=float(curr.get("wind_speed_10m", 2.2)),
                            solar_radiation_mj=float(radiation),
                            precipitation_mm=float(curr.get("precipitation", 0.0)),
                            cloud_cover_pct=float(curr.get("cloud_cover", 20.0))
                        )
                        self._cached_telemetry = telemetry
                        self._cache_timestamp = time.time()
                        return telemetry
            except Exception:
                if attempt < max_retries:
                    await asyncio.sleep(0.3 * attempt)
                continue

        # Fallback to realistic Da Lat highland microclimate benchmark
        fallback = WeatherTelemetry(
            temp_c=23.8,
            temp_max=27.5,
            temp_min=17.0,
            humidity_percent=66.0,
            wind_speed_ms=2.0,
            solar_radiation_mj=17.8,
            precipitation_mm=0.0,
            cloud_cover_pct=25.0
        )
        return fallback
