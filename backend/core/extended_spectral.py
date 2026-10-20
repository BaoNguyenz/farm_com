"""
Extended Spectral Vegetation and Hydrological Indices Module.
Provides advanced multispectral indicators for precision agronomy,
chlorophyll monitoring, canopy water stress, and biophysical modeling.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class SpectralBands:
    """Multispectral reflectances corresponding to Sentinel-2 MSI bands."""
    blue: float        # B2 (490 nm)
    green: float       # B3 (560 nm)
    red: float         # B4 (665 nm)
    red_edge_1: float  # B5 (705 nm)
    red_edge_2: float  # B6 (740 nm)
    red_edge_3: float  # B7 (783 nm)
    nir: float         # B8 (842 nm)
    narrow_nir: float  # B8A (865 nm)
    swir_1: float      # B11 (1610 nm)
    swir_2: float      # B12 (2190 nm)


@dataclass
class CanopyClassification:
    """Classified canopy state from calculated indices."""
    vigor_status: str
    water_stress_status: str
    chlorophyll_status: str
    recommendation: str


class ExtendedSpectralEngine:
    """Computes specialized spectral indexes for remote sensing agronomy."""

    def __init__(self, soil_factor_l: float = 0.5):
        self.soil_factor_l = soil_factor_l
        self.min_reflectance = 1e-6

    def compute_ndvi(self, bands: SpectralBands) -> float:
        """Normalized Difference Vegetation Index (Rouse et al., 1974)."""
        denom = bands.nir + bands.red
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.nir - bands.red) / denom

    def compute_gndvi(self, bands: SpectralBands) -> float:
        """Green Normalized Difference Vegetation Index (Gitelson et al., 1996)."""
        denom = bands.nir + bands.green
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.nir - bands.green) / denom

    def compute_ndre(self, bands: SpectralBands) -> float:
        """Normalized Difference Red Edge Index for mid-to-late season canopy."""
        denom = bands.nir + bands.red_edge_1
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.nir - bands.red_edge_1) / denom

    def compute_ndre2(self, bands: SpectralBands) -> float:
        """Alternative Red Edge Index using B6 (740 nm)."""
        denom = bands.nir + bands.red_edge_2
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.nir - bands.red_edge_2) / denom

    def compute_savi(self, bands: SpectralBands) -> float:
        """Soil Adjusted Vegetation Index with calibration factor L (Huete, 1988)."""
        l = self.soil_factor_l
        denom = bands.nir + bands.red + l
        if abs(denom) < self.min_reflectance:
            return 0.0
        return ((bands.nir - bands.red) / denom) * (1.0 + l)

    def compute_msavi2(self, bands: SpectralBands) -> float:
        """Modified Soil Adjusted Vegetation Index 2 (Qi et al., 1994)."""
        term = 2.0 * bands.nir + 1.0
        val = term * term - 8.0 * (bands.nir - bands.red)
        if val < 0:
            return 0.0
        return (term - math.sqrt(val)) / 2.0

    def compute_evi(self, bands: SpectralBands) -> float:
        """Enhanced Vegetation Index (Huete et al., 2002)."""
        gain = 2.5
        c1, c2, l = 6.0, 7.5, 1.0
        denom = bands.nir + c1 * bands.red - c2 * bands.blue + l
        if abs(denom) < self.min_reflectance:
            return 0.0
        return gain * ((bands.nir - bands.red) / denom)

    def compute_evi2(self, bands: SpectralBands) -> float:
        """Two-band Enhanced Vegetation Index without blue band dependency."""
        gain = 2.5
        denom = bands.nir + 2.4 * bands.red + 1.0
        if abs(denom) < self.min_reflectance:
            return 0.0
        return gain * ((bands.nir - bands.red) / denom)

    def compute_ndwi_gao(self, bands: SpectralBands) -> float:
        """Normalized Difference Water Index for canopy liquid water (Gao, 1996)."""
        denom = bands.nir + bands.swir_1
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.nir - bands.swir_1) / denom

    def compute_ndwi_mcfeeters(self, bands: SpectralBands) -> float:
        """Normalized Difference Water Index for surface water delineation."""
        denom = bands.green + bands.nir
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.green - bands.nir) / denom

    def compute_msi(self, bands: SpectralBands) -> float:
        """Moisture Stress Index (Rock et al., 1986)."""
        if abs(bands.nir) < self.min_reflectance:
            return 0.0
        return bands.swir_1 / bands.nir

    def compute_cigreen(self, bands: SpectralBands) -> float:
        """Chlorophyll Index Green (Gitelson et al., 2005)."""
        if abs(bands.green) < self.min_reflectance:
            return 0.0
        return (bands.nir / bands.green) - 1.0

    def compute_cirededge(self, bands: SpectralBands) -> float:
        """Chlorophyll Index Red Edge (Gitelson et al., 2005)."""
        if abs(bands.red_edge_1) < self.min_reflectance:
            return 0.0
        return (bands.nir / bands.red_edge_1) - 1.0

    def compute_mtci(self, bands: SpectralBands) -> float:
        """MERIS Terrestrial Chlorophyll Index (Dash & Curran, 2004)."""
        denom = bands.red_edge_1 - bands.red
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (bands.red_edge_2 - bands.red_edge_1) / denom

    def compute_nddi(self, bands: SpectralBands) -> float:
        """Normalized Difference Drought Index (Gu et al., 2007)."""
        ndvi = self.compute_ndvi(bands)
        ndwi = self.compute_ndwi_gao(bands)
        denom = ndvi + ndwi
        if abs(denom) < self.min_reflectance:
            return 0.0
        return (ndvi - ndwi) / denom

    def calculate_all_indices(self, bands: SpectralBands) -> Dict[str, float]:
        """Calculates a comprehensive dictionary of all spectral indices."""
        return {
            "ndvi": round(self.compute_ndvi(bands), 4),
            "gndvi": round(self.compute_gndvi(bands), 4),
            "ndre": round(self.compute_ndre(bands), 4),
            "ndre2": round(self.compute_ndre2(bands), 4),
            "savi": round(self.compute_savi(bands), 4),
            "msavi2": round(self.compute_msavi2(bands), 4),
            "evi": round(self.compute_evi(bands), 4),
            "evi2": round(self.compute_evi2(bands), 4),
            "ndwi_canopy": round(self.compute_ndwi_gao(bands), 4),
            "ndwi_water": round(self.compute_ndwi_mcfeeters(bands), 4),
            "msi": round(self.compute_msi(bands), 4),
            "ci_green": round(self.compute_cigreen(bands), 4),
            "ci_rededge": round(self.compute_cirededge(bands), 4),
            "mtci": round(self.compute_mtci(bands), 4),
            "nddi": round(self.compute_nddi(bands), 4),
        }

    def classify_crop_health(self, indices: Dict[str, float]) -> CanopyClassification:
        """Classifies crop vigor, moisture stress, and chlorophyll adequacy."""
        ndvi = indices.get("ndvi", 0.0)
        ndwi = indices.get("ndwi_canopy", 0.0)
        ndre = indices.get("ndre", 0.0)

        # Canopy vigor assessment
        if ndvi > 0.70:
            vigor = "DENSE_EXCELLENT"
        elif ndvi > 0.50:
            vigor = "MODERATE_GOOD"
        elif ndvi > 0.30:
            vigor = "SPARSE_WATCH"
        else:
            vigor = "CRITICAL_POOR"

        # Moisture stress assessment
        if ndwi > 0.30:
            moisture = "OPTIMAL_TURGID"
        elif ndwi > 0.10:
            moisture = "MILD_DEFICIT"
        elif ndwi > -0.10:
            moisture = "MODERATE_WATER_STRESS"
        else:
            moisture = "SEVERE_DESICCATION"

        # Chlorophyll assessment
        if ndre > 0.45:
            chlorophyll = "HIGH_NITROGEN_SATURATED"
        elif ndre > 0.28:
            chlorophyll = "NORMAL_HEALTHY"
        else:
            chlorophyll = "CHLOROSIS_DEFICIENT"

        # Synthesis recommendation
        if moisture in ("MODERATE_WATER_STRESS", "SEVERE_DESICCATION"):
            rec = "Trigger priority irrigation cycle. Water deficit detected."
        elif chlorophyll == "CHLOROSIS_DEFICIENT":
            rec = "Schedule targeted foliar nitrogen or micronutrient spray."
        elif vigor == "CRITICAL_POOR":
            rec = "Inspect plot for potential root rot or emergent pest infestation."
        else:
            rec = "Normal growth conditions. Maintain baseline regime."
