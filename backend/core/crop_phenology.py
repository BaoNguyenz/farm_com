"""
Crop Phenology and Thermal Degree-Day Growth Stage Engine.
Simulates crop growth phases, growing degree day (GDD) accumulation,
dynamic root depth expansion, and stage-specific crop coefficients (Kc).
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import math


class PhenologicalStage(Enum):
    """Universal crop growth stages based on the BBCH scale."""
    DORMANT_SOWING = "Dormant / Sowing (Stage 00-09)"
    EMERGENCE = "Emergence / Seedling (Stage 10-19)"
    TILLERING_VEGETATIVE = "Tillering / Rapid Vegetative (Stage 20-39)"
    STEM_ELONGATION = "Stem Elongation / Jointing (Stage 40-49)"
    BOOTING_FLOWERING = "Booting / Anthesis Flowering (Stage 50-69)"
    GRAIN_FILL_FRUITING = "Grain Filling / Fruit Expansion (Stage 70-79)"
