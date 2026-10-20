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
