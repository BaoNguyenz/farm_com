"""
Copernicus Sentinel-2 Satellite Client
Fetches multispectral bands (B2 through B12) or generates high-fidelity
spatial-temporal synthetic reflectances for development and offline testing.
"""
from typing import Dict, Any
import random
import time


class SatelliteClient:
    """
    Sentinel-2 L2A Client providing top-of-canopy surface reflectance,
    biophysical band synthesis, and cloud contamination quality assessment.
    """
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.is_authenticated = bool(client_id and client_secret)

    def assess_cloud_contamination(self, cloud_cover_pct: float) -> Dict[str, Any]:
        """
        Evaluates whether optical satellite pass is suitable for spectral indexing.
        """
        is_obscured = cloud_cover_pct > 35.0
        quality_score = max(0.0, 1.0 - (cloud_cover_pct / 100.0))
        return {
            "cloud_cover_pct": cloud_cover_pct,
            "cloud_masked": is_obscured,
            "usable_for_indices": not is_obscured,
            "optical_quality_score": round(quality_score, 2),
        }

    async def get_zone_spectral_bands(self, lat: float, lon: float, zone_id: str) -> Dict[str, Any]:
        """
        Retrieves Surface Reflectance bands:
        - B2: Blue (0.490 um)
        - B4: Red (0.665 um)
        - B8: NIR (0.842 um)
        - B11: SWIR (1.610 um)
        """
        full_bands = await self.get_full_multispectral_bands(zone_id)
        return {
            "B2_blue": full_bands["blue"],
            "B4_red": full_bands["red"],
            "B8_nir": full_bands["nir"],
            "B11_swir": full_bands["swir_1"],
            "source": "Sentinel-2 L2A (Synthesized/Cache)"
        }

    async def get_full_multispectral_bands(
        self, zone_id: str, cloud_cover_pct: float = 12.0
    ) -> Dict[str, float]:
        """
        Generates or queries full 10-band Sentinel-2 reflectance matrix
        compatible with the ExtendedSpectralEngine dataclass.
        """
        random.seed(f"{zone_id}-{int(time.time() // 3600)}")
        is_stressed = (zone_id in ("Z_2_1", "PLOT_2_1"))

        if is_stressed:
            blue = 0.08 + random.uniform(-0.01, 0.01)
            green = 0.09 + random.uniform(-0.01, 0.01)
            red = 0.12 + random.uniform(-0.01, 0.02)
            re1 = 0.16 + random.uniform(-0.01, 0.02)
            re2 = 0.22 + random.uniform(-0.02, 0.02)
            re3 = 0.26 + random.uniform(-0.02, 0.02)
            nir = 0.28 + random.uniform(-0.02, 0.02)
            narrow_nir = 0.29 + random.uniform(-0.02, 0.02)
            swir1 = 0.22 + random.uniform(-0.01, 0.02)
            swir2 = 0.15 + random.uniform(-0.01, 0.02)
        else:
            blue = 0.03 + random.uniform(-0.005, 0.005)
            green = 0.08 + random.uniform(-0.01, 0.01)
            red = 0.04 + random.uniform(-0.01, 0.01)
            re1 = 0.18 + random.uniform(-0.01, 0.02)
            re2 = 0.28 + random.uniform(-0.02, 0.02)
            re3 = 0.35 + random.uniform(-0.02, 0.02)
            nir = 0.55 + random.uniform(-0.03, 0.04)
            narrow_nir = 0.57 + random.uniform(-0.03, 0.03)
            swir1 = 0.14 + random.uniform(-0.02, 0.02)
            swir2 = 0.07 + random.uniform(-0.01, 0.01)

        return {
            "blue": round(max(0.01, blue), 3),
            "green": round(max(0.01, green), 3),
            "red": round(max(0.01, red), 3),
            "red_edge_1": round(max(0.01, re1), 3),
            "red_edge_2": round(max(0.01, re2), 3),
            "red_edge_3": round(max(0.01, re3), 3),
            "nir": round(max(0.01, nir), 3),
            "narrow_nir": round(max(0.01, narrow_nir), 3),
            "swir_1": round(max(0.01, swir1), 3),
            "swir_2": round(max(0.01, swir2), 3),
        }
