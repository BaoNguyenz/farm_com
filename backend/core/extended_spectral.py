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
