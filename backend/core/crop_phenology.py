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
        base_temperature=12.0,
        cutoff_temperature=32.0,
        optimal_temperature=24.0,
        gdd_emergence=120.0,
        gdd_vegetative=700.0,
        gdd_flowering=1200.0,
        gdd_maturity=2200.0,
        kc_initial=0.90,
        kc_mid=0.95,
        kc_end=0.85,
        max_root_depth_meters=1.50,
        initial_root_depth_meters=0.30,
    ),
}


class PhenologyEngine:
    """Calculates thermal time, stage transitions, dynamic Kc, and root growth."""

    def __init__(self, crop_name: str = "maize"):
        key = crop_name.lower().strip()
        if key not in CROP_DATABASE:
            self.params = CROP_DATABASE["maize"]
        else:
            self.params = CROP_DATABASE[key]

        self.accumulated_gdd: float = 0.0
        self.days_since_planting: int = 0

    def compute_daily_gdd(self, t_max: float, t_min: float) -> float:
        """Standard agronomic GDD equation with upper cutoff and lower base limits."""
        t_base = self.params.base_temperature
        t_cut = self.params.cutoff_temperature

        # Apply boundary constraints
        t_max_adj = min(max(t_max, t_base), t_cut)
        t_min_adj = max(t_min, t_base)

        t_mean = (t_max_adj + t_min_adj) / 2.0
        daily_gdd = max(0.0, t_mean - t_base)
        return round(daily_gdd, 2)

    def advance_day(self, t_max: float, t_min: float) -> float:
        """Advances the simulation by one calendar day with given temperatures."""
        gdd = self.compute_daily_gdd(t_max, t_min)
        self.accumulated_gdd += gdd
        self.days_since_planting += 1
        return gdd

    def get_current_stage(self) -> PhenologicalStage:
        """Determines current phenological stage based on accumulated GDD."""
        gdd = self.accumulated_gdd
        p = self.params

        if gdd < p.gdd_emergence:
            return PhenologicalStage.DORMANT_SOWING
        elif gdd < p.gdd_emergence * 1.8:
            return PhenologicalStage.EMERGENCE
        elif gdd < p.gdd_vegetative:
            return PhenologicalStage.TILLERING_VEGETATIVE
        elif gdd < p.gdd_vegetative * 1.4:
            return PhenologicalStage.STEM_ELONGATION
        elif gdd < p.gdd_flowering:
            return PhenologicalStage.BOOTING_FLOWERING
        elif gdd < p.gdd_maturity * 0.85:
            return PhenologicalStage.GRAIN_FILL_FRUITING
        elif gdd < p.gdd_maturity:
            return PhenologicalStage.RIPENING_MATURITY
        else:
            return PhenologicalStage.SENESCENCE_HARVEST

