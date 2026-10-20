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
