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
    RIPENING_MATURITY = "Ripening / Physiological Maturity (Stage 80-89)"
    SENESCENCE_HARVEST = "Senescence / Ready for Harvest (Stage 90-99)"


@dataclass
class CropParameters:
    """Agronomic and thermal characteristics for a specific crop species."""
    crop_name: str
    base_temperature: float     # Tbase (°C) below which development stops
    cutoff_temperature: float   # Tcutoff (°C) above which development plateaus
    optimal_temperature: float  # Topt (°C) for maximum metabolic efficiency
    gdd_emergence: float        # Accumulated GDD for emergence
    gdd_vegetative: float       # Accumulated GDD for vegetative stage
    gdd_flowering: float        # Accumulated GDD for flowering stage
    gdd_maturity: float         # Accumulated GDD for full maturity
    kc_initial: float           # FAO-56 Kc ini (initial stage)
    kc_mid: float               # FAO-56 Kc mid (mid-season peak)
    kc_end: float               # FAO-56 Kc end (late season harvest)
    max_root_depth_meters: float
    initial_root_depth_meters: float


# Benchmark parameters for primary commercial crops
CROP_DATABASE: Dict[str, CropParameters] = {
    "maize": CropParameters(
        crop_name="Maize / Corn",
        base_temperature=10.0,
        cutoff_temperature=30.0,
        optimal_temperature=25.0,
        gdd_emergence=80.0,
        gdd_vegetative=450.0,
        gdd_flowering=850.0,
        gdd_maturity=1450.0,
        kc_initial=0.30,
        kc_mid=1.20,
        kc_end=0.35,
        max_root_depth_meters=1.20,
        initial_root_depth_meters=0.15,
    ),
    "rice": CropParameters(
        crop_name="Paddy Rice",
        base_temperature=10.0,
        cutoff_temperature=35.0,
        optimal_temperature=28.0,
        gdd_emergence=90.0,
        gdd_vegetative=500.0,
        gdd_flowering=950.0,
        gdd_maturity=1600.0,
        kc_initial=1.05,
        kc_mid=1.20,
        kc_end=0.90,
        max_root_depth_meters=0.60,
        initial_root_depth_meters=0.10,
    ),
    "coffee": CropParameters(
        crop_name="Coffee Robusta / Arabica",
