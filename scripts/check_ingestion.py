#!/usr/bin/env python3
"""
External Ingestion Pipeline Diagnostic and Health Check Tool.
Tests connectivity to Open-Meteo API, verifies Sentinel-2 band synthesis,
and prints live telemetry status for farm operators.
"""

import sys
import asyncio
from pathlib import Path

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.ingestion.weather_client import WeatherClient  # noqa: E402
from backend.ingestion.satellite_client import SatelliteClient  # noqa: E402

# Configure UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def run_diagnostics():
    print("=" * 60)
    print("🛰️  FARM_COM DATA INGESTION & SATELLITE HEALTH CHECK")
    print("=" * 60)

    # 1. Weather Client
    print("\n[1/2] Connecting to Open-Meteo API...")
    weather_client = WeatherClient()
    weather = await weather_client.fetch_current_weather()
    print(f"   • Ambient Temperature : {weather.temp_c}°C (Max: {weather.temp_max}°C, Min: {weather.temp_min}°C)")
    print(f"   • Relative Humidity   : {weather.humidity_percent}%")
    print(f"   • Wind Speed (10m)    : {weather.wind_speed_ms} m/s")
    print(f"   • Solar Radiation     : {weather.solar_radiation_mj} MJ/m²")
    print(f"   • Cloud Cover         : {weather.cloud_cover_pct}%")
    print(f"   • Cache Status        : {'ACTIVE & VALID' if weather_client.is_cache_valid() else 'EXPIRED'}")

    # 2. Satellite Client
    print("\n[2/2] Generating Sentinel-2 L2A Top-of-Canopy Reflectances...")
    sat_client = SatelliteClient()
    cloud_eval = sat_client.assess_cloud_contamination(weather.cloud_cover_pct)
    print(f"   • Optical Pass Quality: Score {cloud_eval['optical_quality_score']} (Cloud Masked: {cloud_eval['cloud_masked']})")

    bands = await sat_client.get_full_multispectral_bands("PLOT_0_0", weather.cloud_cover_pct)
    print(f"   • Band B4 (Red 665nm) : {bands['red']}")
    print(f"   • Band B8 (NIR 842nm) : {bands['nir']}")
    print(f"   • Band B11 (SWIR 1.6u): {bands['swir_1']}")

    ndvi_approx = (bands["nir"] - bands["red"]) / max(1e-5, (bands["nir"] + bands["red"]))
    print(f"   • Computed Base NDVI  : {ndvi_approx:.3f}")

    print("\n✅ Ingestion pipeline diagnostic completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_diagnostics())
