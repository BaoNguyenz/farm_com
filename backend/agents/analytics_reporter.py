"""
Multi-Agent Farm Intelligence and Executive Analytics Reporter.
Synthesizes telemetry, spectral vegetative index observations,
agronomy health diagnoses, and market intelligence into comprehensive audits.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class AgronomyHealthMetric:
    """Individual plot agronomy index metric."""
    plot_id: str
    crop_type: str
    ndvi_score: float
    ndwi_score: float
    ndre_score: float
    chlorophyll_level: str
    water_stress_status: str

