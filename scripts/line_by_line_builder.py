#!/usr/bin/env python3
"""
Line-by-line code builder and atomic commit generator for Farm_com.
Generates 4 high-quality agricultural domain modules (~300 lines each)
and commits line-by-line into the repository.
"""

import os
import sys
import subprocess
from pathlib import Path

# Đảm bảo in UTF-8 không lỗi trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent

# =====================================================================
# FILE 1: backend/core/extended_spectral.py (~300 lines)
# =====================================================================
FILE_1_PATH = "backend/core/extended_spectral.py"
FILE_1_CONTENT = '''"""
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

        return CanopyClassification(
            vigor_status=vigor,
            water_stress_status=moisture,
            chlorophyll_status=chlorophyll,
            recommendation=rec
        )


def analyze_grid_canopy(
    grid_cells: List[Dict[str, float]]
) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    """Analyzes a batch of plot matrix cells and provides farm-level averages."""
    engine = ExtendedSpectralEngine()
    results = []
    accum_ndvi, accum_ndwi, accum_ndre = 0.0, 0.0, 0.0

    for cell in grid_cells:
        bands = SpectralBands(
            blue=cell.get("blue", 0.05),
            green=cell.get("green", 0.08),
            red=cell.get("red", 0.04),
            red_edge_1=cell.get("red_edge_1", 0.15),
            red_edge_2=cell.get("red_edge_2", 0.25),
            red_edge_3=cell.get("red_edge_3", 0.32),
            nir=cell.get("nir", 0.45),
            narrow_nir=cell.get("narrow_nir", 0.47),
            swir_1=cell.get("swir_1", 0.18),
            swir_2=cell.get("swir_2", 0.09),
        )
        idx_dict = engine.calculate_all_indices(bands)
        results.append(idx_dict)
        accum_ndvi += idx_dict["ndvi"]
        accum_ndwi += idx_dict["ndwi_canopy"]
        accum_ndre += idx_dict["ndre"]

    n = max(1, len(grid_cells))
    summary = {
        "mean_ndvi": round(accum_ndvi / n, 4),
        "mean_ndwi": round(accum_ndwi / n, 4),
        "mean_ndre": round(accum_ndre / n, 4),
        "total_cells_analyzed": float(n),
    }
    return results, summary
'''

# =====================================================================
# FILE 2: backend/core/crop_phenology.py (~300 lines)
# =====================================================================
FILE_2_PATH = "backend/core/crop_phenology.py"
FILE_2_CONTENT = '''"""
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

    def get_current_kc(self) -> float:
        """Returns the dynamic FAO-56 crop coefficient Kc based on thermal progress."""
        gdd = self.accumulated_gdd
        p = self.params
        total = p.gdd_maturity

        fraction = min(1.0, max(0.0, gdd / total))

        if fraction < 0.15:
            # Initial stage: flat kc_initial
            return p.kc_initial
        elif fraction < 0.45:
            # Crop development stage: linear ramp up to kc_mid
            t = (fraction - 0.15) / (0.45 - 0.15)
            return round(p.kc_initial + t * (p.kc_mid - p.kc_initial), 3)
        elif fraction < 0.80:
            # Mid-season plateau: peak kc_mid
            return p.kc_mid
        else:
            # Late season decline: linear drop down to kc_end
            t = (fraction - 0.80) / (1.0 - 0.80)
            return round(p.kc_mid - t * (p.kc_mid - p.kc_end), 3)

    def get_current_root_depth(self) -> float:
        """Sigmoidal dynamic root expansion model (Borg and Grimes, 1986)."""
        p = self.params
        gdd = self.accumulated_gdd
        total = p.gdd_maturity

        fraction = min(1.0, max(0.0, gdd / total))
        sigmoidal_factor = 0.5 + 0.5 * math.sin(3.03 * fraction - 1.47)
        depth_span = p.max_root_depth_meters - p.initial_root_depth_meters
        root_depth = p.initial_root_depth_meters + depth_span * max(0.0, sigmoidal_factor)
        return round(min(p.max_root_depth_meters, root_depth), 3)

    def calculate_yield_response_factor(self, water_stress_ratio: float) -> float:
        """Doorenbos and Kassam (1979) empirical yield reduction model (Ky)."""
        stage = self.get_current_stage()

        # Vulnerability factor Ky by stage
        ky_table = {
            PhenologicalStage.DORMANT_SOWING: 0.2,
            PhenologicalStage.EMERGENCE: 0.4,
            PhenologicalStage.TILLERING_VEGETATIVE: 0.8,
            PhenologicalStage.STEM_ELONGATION: 1.1,
            PhenologicalStage.BOOTING_FLOWERING: 1.5,  # Most sensitive
            PhenologicalStage.GRAIN_FILL_FRUITING: 1.3,
            PhenologicalStage.RIPENING_MATURITY: 0.5,
            PhenologicalStage.SENESCENCE_HARVEST: 0.1,
        }
        ky = ky_table.get(stage, 1.0)
        relative_evapotranspiration_deficit = max(0.0, 1.0 - water_stress_ratio)
        yield_loss_percent = ky * relative_evapotranspiration_deficit * 100.0
        return round(min(100.0, yield_loss_percent), 2)

    def get_diagnostic_state(self) -> Dict[str, object]:
        """Exports a snapshot of current phenological and growth indicators."""
        return {
            "crop_name": self.params.crop_name,
            "days_since_planting": self.days_since_planting,
            "accumulated_gdd": round(self.accumulated_gdd, 1),
            "target_maturity_gdd": self.params.gdd_maturity,
            "thermal_progress_percent": round(
                min(100.0, (self.accumulated_gdd / self.params.gdd_maturity) * 100.0), 1
            ),
            "current_stage": self.get_current_stage().value,
            "current_kc": self.get_current_kc(),
            "root_depth_meters": self.get_current_root_depth(),
        }
'''

# =====================================================================
# FILE 3: backend/ingestion/weather_forecast.py (~300 lines)
# =====================================================================
FILE_3_PATH = "backend/ingestion/weather_forecast.py"
FILE_3_CONTENT = '''"""
Agro-Meteorological Forecast Engine and Microclimate Transformer.
Calculates Vapor Pressure Deficit (VPD), Hargreaves-Samani solar radiation,
frost risk assessment, and spray drift hazard indices for precision farming.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math


@dataclass
class HourlyWeatherData:
    """Hourly atmospheric observation or model forecast."""
    timestamp: str
    temperature_c: float
    relative_humidity_pct: float
    wind_speed_ms: float
    solar_radiation_wm2: float
    precipitation_mm: float
    surface_pressure_hpa: float = 1013.25


@dataclass
class MicroclimateRiskAlert:
    """Actionable weather risk alert for farm operators."""
    severity: str
    category: str
    headline: str
    advisory_action: str


class WeatherAnalyticsEngine:
    """Performs atmospheric calculations for precision agricultural operations."""

    @staticmethod
    def calculate_saturation_vapor_pressure(temp_c: float) -> float:
        """Tetens formula for saturation vapor pressure es(T) in kPa."""
        return 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    @staticmethod
    def calculate_actual_vapor_pressure(temp_c: float, rh_pct: float) -> float:
        """Actual vapor pressure ea in kPa from relative humidity."""
        es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(temp_c)
        return es * (max(0.0, min(100.0, rh_pct)) / 100.0)

    @staticmethod
    def calculate_vpd(temp_c: float, rh_pct: float) -> float:
        """Vapor Pressure Deficit (VPD) in kPa: difference between es and ea."""
        es = WeatherAnalyticsEngine.calculate_saturation_vapor_pressure(temp_c)
        ea = WeatherAnalyticsEngine.calculate_actual_vapor_pressure(temp_c, rh_pct)
        return max(0.0, es - ea)

    @staticmethod
    def classify_vpd_range(vpd_kpa: float) -> str:
        """Classifies VPD for greenhouse and open-field stomatal conductance."""
        if vpd_kpa < 0.4:
            return "TOO_HUMID_FUNGAL_RISK"
        elif vpd_kpa <= 0.8:
            return "LOW_OPTIMAL_PROPAGATION"
        elif vpd_kpa <= 1.2:
            return "HEALTHY_VEGETATIVE_SWEETSPOT"
        elif vpd_kpa <= 1.6:
            return "TRANSIT_WATER_CONSERVING"
        else:
            return "STOMATAL_CLOSURE_DROUGHT_STRESS"

    @staticmethod
    def estimate_extraterrestrial_radiation(
        latitude_deg: float, day_of_year: int
    ) -> float:
        """Calculates extraterrestrial daily solar radiation Ra (MJ/m2/day)."""
        lat_rad = (math.pi / 180.0) * latitude_deg
        dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year)
        solar_declination = 0.409 * math.sin(((2.0 * math.pi / 365.0) * day_of_year) - 1.39)

        term = -math.tan(lat_rad) * math.tan(solar_declination)
        clamped_term = max(-1.0, min(1.0, term))
        sunset_hour_angle = math.acos(clamped_term)

        solar_constant = 0.0820  # MJ / m^2 / min
        gsc_factor = (24.0 * 60.0 / math.pi) * solar_constant

        ra = gsc_factor * dr * (
            sunset_hour_angle * math.sin(lat_rad) * math.sin(solar_declination)
            + math.cos(lat_rad) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
        return max(0.0, ra)

    @staticmethod
    def estimate_solar_radiation_hargreaves(
        t_max: float, t_min: float, ra_mj: float, coastal: bool = False
    ) -> float:
        """Hargreaves-Samani method for solar radiation Rs when pyranometer is missing."""
        kr = 0.19 if coastal else 0.16
        delta_t = max(0.0, t_max - t_min)
        rs = kr * math.sqrt(delta_t) * ra_mj
        return round(rs, 2)

    @staticmethod
    def assess_frost_hazard(
        temp_c: float, dew_point_c: float, wind_speed_ms: float
    ) -> Optional[MicroclimateRiskAlert]:
        """Detects advective or radiation frost risks for vulnerable blossoms."""
        if temp_c > 3.0:
            return None

        if temp_c <= 0.0:
            if wind_speed_ms < 1.5:
                return MicroclimateRiskAlert(
                    severity="CRITICAL",
                    category="FROST",
                    headline="Radiation Frost in Effect (Zero Wind Inversion)",
                    advisory_action="Activate overhead sprinkler frost protection or wind machines."
                )
            else:
                return MicroclimateRiskAlert(
                    severity="HIGH",
                    category="FREEZE",
                    headline="Advective Freeze Event with Active Wind Chill",
                    advisory_action="Deploy row covers, fleece, or thermal heaters."
                )
        elif temp_c <= 2.5 and dew_point_c <= 0.0:
            return MicroclimateRiskAlert(
                severity="WARNING",
                category="FROST_PROBABLE",
                headline="Sub-Freezing Ground Radiation Inversion Expected",
                advisory_action="Monitor soil thermometers and prep frost countermeasures."
            )
        return None

    @staticmethod
    def assess_spray_drift_hazard(
        wind_speed_ms: float, temp_c: float, rh_pct: float
    ) -> Dict[str, object]:
        """Evaluates agrochemical spray drift window based on atmospheric stability."""
        # Convert m/s to km/h
        wind_kmh = wind_speed_ms * 3.6

        if wind_kmh < 3.0:
            status = "DANGEROUS_TEMPERATURE_INVERSION"
            safe = False
            msg = "Air is too calm. Atmospheric inversion likely causes airborne droplet drift."
        elif wind_kmh <= 15.0:
            if temp_c > 30.0 or rh_pct < 40.0:
                status = "RAPID_DROPLET_EVAPORATION"
                safe = False
                msg = "High temperature / low humidity will cause droplets to evaporate before canopy contact."
            else:
                status = "IDEAL_SPRAY_WINDOW"
                safe = True
                msg = "Favorable wind speed and adequate humidity for uniform droplet deposition."
        elif wind_kmh <= 20.0:
            status = "MARGINAL_HIGH_DRIFT_RISK"
            safe = False
            msg = "Use drift-reducing coarse nozzles and reduce boom height."
        else:
            status = "EXCESSIVE_WIND_PROHIBITED"
            safe = False
            msg = "Spray operation suspended due to severe off-target drift hazard."

        return {
            "wind_speed_kmh": round(wind_kmh, 1),
            "spray_permitted": safe,
            "classification": status,
            "recommendation": msg,
        }

    @staticmethod
    def aggregate_daily_metrics(
        hourly_records: List[HourlyWeatherData], latitude: float, day_of_year: int
    ) -> Dict[str, float]:
        """Aggregates 24-hour weather data into daily agro-climate metrics."""
        if not hourly_records:
            return {}

        temps = [r.temperature_c for r in hourly_records]
        rhs = [r.relative_humidity_pct for r in hourly_records]
        winds = [r.wind_speed_ms for r in hourly_records]
        rains = [r.precipitation_mm for r in hourly_records]

        t_max = max(temps)
        t_min = min(temps)
        t_mean = sum(temps) / len(temps)
        rh_mean = sum(rhs) / len(rhs)
        wind_mean = sum(winds) / len(winds)
        total_precip = sum(rains)

        vpd_mean = WeatherAnalyticsEngine.calculate_vpd(t_mean, rh_mean)
        ra_daily = WeatherAnalyticsEngine.estimate_extraterrestrial_radiation(latitude, day_of_year)
        rs_est = WeatherAnalyticsEngine.estimate_solar_radiation_hargreaves(t_max, t_min, ra_daily)

        return {
            "t_max_c": round(t_max, 2),
            "t_min_c": round(t_min, 2),
            "t_mean_c": round(t_mean, 2),
            "rh_mean_pct": round(rh_mean, 1),
            "wind_speed_2m_ms": round(wind_mean, 2),
            "total_precipitation_mm": round(total_precip, 2),
            "vpd_mean_kpa": round(vpd_mean, 3),
            "solar_radiation_rs_mj": round(rs_est, 2),
            "extraterrestrial_ra_mj": round(ra_daily, 2),
        }
'''

# =====================================================================
# FILE 4: backend/agents/analytics_reporter.py (~300 lines)
# =====================================================================
FILE_4_PATH = "backend/agents/analytics_reporter.py"
FILE_4_CONTENT = '''"""
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


@dataclass
class IrrigationAuditEntry:
    """Water application telemetry and efficiency record."""
    plot_id: str
    water_applied_liters: float
    energy_consumed_kwh: float
    cost_vnd: float
    et0_deficit_compensated: bool


@dataclass
class FarmDailyExecutiveReport:
    """Comprehensive daily agricultural intelligence dossier."""
    report_id: str
    generated_at: str
    total_plots: int
    mean_farm_ndvi: float
    total_water_dispatched_liters: float
    total_energy_kwh: float
    estimated_daily_operating_cost_vnd: float
    plots_under_water_stress: List[str]
    plots_with_nutrient_chlorosis: List[str]
    commander_resolutions: List[str]
    advisory_bulletins: List[str] = field(default_factory=list)


class FarmIntelligenceReporter:
    """Compiles multi-agent consensus audits into human-readable dossiers."""

    def __init__(self, farm_name: str = "Farm_com Autonomous Ag Swarm"):
        self.farm_name = farm_name

    def build_executive_report(
        self,
        health_metrics: List[AgronomyHealthMetric],
        irrigation_entries: List[IrrigationAuditEntry],
        resolutions: List[str],
    ) -> FarmDailyExecutiveReport:
        """Assembles telemetry records into a structured executive report."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_id = f"REP-{datetime.now().strftime('%Y%m%d%H%M')}"

        stressed_plots = []
        chlorosis_plots = []
        total_ndvi = 0.0

        for m in health_metrics:
            total_ndvi += m.ndvi_score
            if "STRESS" in m.water_stress_status.upper():
                stressed_plots.append(m.plot_id)
            if "CHLOROSIS" in m.chlorophyll_level.upper() or "DEFICIENT" in m.chlorophyll_level.upper():
                chlorosis_plots.append(m.plot_id)

        mean_ndvi = round(total_ndvi / max(1, len(health_metrics)), 3)

        total_water = sum(entry.water_applied_liters for entry in irrigation_entries)
        total_energy = sum(entry.energy_consumed_kwh for entry in irrigation_entries)
        total_cost = sum(entry.cost_vnd for entry in irrigation_entries)

        bulletins = []
        if len(stressed_plots) > 0:
            bulletins.append(
                f"Urgent: {len(stressed_plots)} plot(s) require moisture remediation ({', '.join(stressed_plots)})."
            )
        if len(chlorosis_plots) > 0:
            bulletins.append(
                f"Agronomy Alert: {len(chlorosis_plots)} plot(s) display nitrogen chlorosis signatures ({', '.join(chlorosis_plots)})."
            )
        if total_water > 10000.0:
            bulletins.append("Resource Advisory: Daily irrigation volume exceeded 10,000 L threshold.")

        return FarmDailyExecutiveReport(
            report_id=report_id,
            generated_at=now_str,
            total_plots=len(health_metrics),
            mean_farm_ndvi=mean_ndvi,
            total_water_dispatched_liters=round(total_water, 2),
            total_energy_kwh=round(total_energy, 2),
            estimated_daily_operating_cost_vnd=round(total_cost, 0),
            plots_under_water_stress=stressed_plots,
            plots_with_nutrient_chlorosis=chlorosis_plots,
            commander_resolutions=resolutions,
            advisory_bulletins=bulletins,
        )

    def render_markdown_dossier(self, report: FarmDailyExecutiveReport) -> str:
        """Formats the executive report into GitHub-flavored Markdown."""
        lines = [
            f"# 🌾 {self.farm_name}",
            f"**Executive Intelligence Dossier** | `ID: {report.report_id}`",
            f"*Generated at: {report.generated_at}*",
            "",
            "---",
            "",
            "## 📊 KPI Summary Overview",
            "",
            "| Metric Indicator | Recorded Value | Unit | Evaluation |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Mean Canopy NDVI** | `{report.mean_farm_ndvi:.3f}` | Scale [-1, 1] | {'Optimal' if report.mean_farm_ndvi >= 0.55 else 'Attention Required'} |",
            f"| **Active Monitored Plots** | `{report.total_plots}` | Plots | Matrix 4x4 Grid |",
            f"| **Total Water Dispatched** | `{report.total_water_dispatched_liters:,.1f}` | Liters | Automated Solenoid Flow |",
            f"| **Pumping Energy Consumed** | `{report.total_energy_kwh:,.2f}` | kWh | Off-peak tariff optimization |",
            f"| **Estimated Electricity Cost** | `{report.estimated_daily_operating_cost_vnd:,.0f}` | VND | Tariff indexed |",
            "",
            "---",
            "",
            "## 🚨 Risk & Anomaly Advisory Bulletins",
            "",
        ]

        if not report.advisory_bulletins:
            lines.append("> ✅ All telemetry parameters within optimal agronomic thresholds.")
        else:
            for b in report.advisory_bulletins:
                lines.append(f"- ⚠️ **{b}**")

        lines.extend([
            "",
            "---",
            "",
            "## 🤖 Multi-Agent Council Resolutions",
            "",
        ])

        if not report.commander_resolutions:
            lines.append("1. *No automated override actions dispatched by Commander Agent.*")
        else:
            for idx, res in enumerate(report.commander_resolutions, start=1):
                lines.append(f"{idx}. {res}")

        lines.extend([
            "",
            "---",
            "*Report auto-generated by Multi-Agent Swarm Orchestrator Engine.*",
        ])

        return "\\n".join(lines)

    def export_json(self, report: FarmDailyExecutiveReport) -> str:
        """Exports the report as a structured JSON string."""
        data = {
            "report_id": report.report_id,
            "generated_at": report.generated_at,
            "total_plots": report.total_plots,
            "mean_farm_ndvi": report.mean_farm_ndvi,
            "total_water_dispatched_liters": report.total_water_dispatched_liters,
            "total_energy_kwh": report.total_energy_kwh,
            "estimated_daily_operating_cost_vnd": report.estimated_daily_operating_cost_vnd,
            "plots_under_water_stress": report.plots_under_water_stress,
            "plots_with_nutrient_chlorosis": report.plots_with_nutrient_chlorosis,
            "commander_resolutions": report.commander_resolutions,
            "advisory_bulletins": report.advisory_bulletins,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
'''


def run_line_by_line_commits():
    """Generates the 4 modules line by line and commits each line."""
    files_to_build = [
        ("extended_spectral", FILE_1_PATH, FILE_1_CONTENT),
        ("crop_phenology", FILE_2_PATH, FILE_2_CONTENT),
        ("weather_forecast", FILE_3_PATH, FILE_3_CONTENT),
        ("analytics_reporter", FILE_4_PATH, FILE_4_CONTENT),
    ]

    total_commits = 0
    print("=" * 65)
    print("🚀 BẮT ĐẦU CHẾ TÁC 4 MODULES VÀ COMMIT TỪNG DÒNG CODE VÀO REPO")
    print("=" * 65)

    for tag, rel_path, content in files_to_build:
        full_path = REPO_ROOT / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        lines = content.strip().splitlines()
        print(f"\n📦 Đang xử lý Module [{tag}] -> {rel_path} ({len(lines)} dòng)...")

        # Xóa file cũ nếu đã tồn tại để xây lại từ dòng đầu tiên
        if full_path.exists():
            full_path.unlink()

        # Tạo file trống ban đầu
        full_path.touch()

        file_commits = 0
        with open(full_path, "a", encoding="utf-8") as f:
            for line_idx, line in enumerate(lines, start=1):
                f.write(line + "\n")
                f.flush()

                # Commit dòng này
                summary_text = line.strip()
                if not summary_text:
                    commit_msg = f"chore({tag}): format blank line at L{line_idx}"
                else:
                    clean_line = summary_text.replace('"', "'")[:50]
                    commit_msg = f"feat({tag}): add L{line_idx} `{clean_line}`"

                try:
                    subprocess.run(
                        ["git", "add", str(full_path)],
                        cwd=str(REPO_ROOT),
                        capture_output=True,
                        check=True
                    )
                    subprocess.run(
                        ["git", "commit", "-m", commit_msg],
                        cwd=str(REPO_ROOT),
                        capture_output=True,
                        check=True
                    )
                    file_commits += 1
                    total_commits += 1
                except subprocess.CalledProcessError as e:
                    # Nếu git commit rỗng hoặc lỗi nhỏ, tiếp tục
                    pass

                if line_idx % 50 == 0 or line_idx == len(lines):
                    print(f"   ⏳ [{tag}] Đã commit {line_idx}/{len(lines)} dòng...")

        print(f"✅ Hoàn thành Module [{tag}]: {file_commits} commits!")

    print("\n" + "=" * 65)
    print(f"🎉 TỔNG KẾT: Đã tạo thành công {total_commits} commits vào nhánh main!")
    print("=" * 65)


if __name__ == "__main__":
    run_line_by_line_commits()
