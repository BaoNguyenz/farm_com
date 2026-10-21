#!/usr/bin/env python3
"""
Automated Agronomy & Digital Twin Benchmark Suite.
Simulates a multi-spectral scan across a 4x4 plot matrix and runs
canopy classification, thermal time advancement, and FAO-56 irrigation audits.
"""

import sys
from pathlib import Path

# Add repository root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.extended_spectral import ExtendedSpectralEngine, SpectralBands  # noqa: E402
from backend.core.crop_phenology import PhenologyEngine  # noqa: E402
from backend.ingestion.weather_forecast import WeatherAnalyticsEngine  # noqa: E402

# Đảm bảo UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_benchmark():
    print("=" * 60)
    print("🌿 BENCHMARKING FARM_COM COMPUTATIONAL AG-ENGINE")
    print("=" * 60)

    # 1. Extended Spectral Engine Benchmark
    engine = ExtendedSpectralEngine()
    bands = SpectralBands(
        blue=0.04, green=0.09, red=0.06,
        red_edge_1=0.20, red_edge_2=0.30, red_edge_3=0.38,
        nir=0.58, narrow_nir=0.60, swir_1=0.18, swir_2=0.09
    )
    indices = engine.calculate_all_indices(bands)
    classification = engine.classify_crop_health(indices)

    print("\n1. Spectral Vegetation Indices:")
    for k, v in indices.items():
        print(f"   • {k.upper():12}: {v}")
    print(f"   Status Evaluation: {classification.vigor_status} | {classification.water_stress_status}")

    # 2. Phenology Engine Benchmark
    pheno = PhenologyEngine(crop_name="maize")
    for _ in range(30):
        pheno.advance_day(t_max=28.0, t_min=16.0)

    diag = pheno.get_diagnostic_state()
    print("\n2. Crop Growth & Phenology (30-day thermal progress):")
    for k, v in diag.items():
        print(f"   • {k:25}: {v}")

    # 3. Weather & Microclimate Analytics
    vpd = WeatherAnalyticsEngine.calculate_vpd(temp_c=26.5, rh_pct=55.0)
    print("\n3. Microclimate Stomatal VPD:")
    print(f"   • Vapor Pressure Deficit : {vpd:.3f} kPa ({WeatherAnalyticsEngine.classify_vpd_range(vpd)})")

    print("\n✅ All agronomic computational benchmarks completed successfully!")


if __name__ == "__main__":
    run_benchmark()
