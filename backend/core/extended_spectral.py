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
