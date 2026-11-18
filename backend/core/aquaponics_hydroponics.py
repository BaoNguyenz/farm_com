r"""
Hydroponic Crop Nitrate Uptake, Vegetative Growth & Alkalinity Buffering Kinetics.

Implements biophysical equations for coupled DWC (Deep Water Culture) / NFT aquaponic beds:
- Michaelis-Menten crop nitrate assimilation:
  $V_{\text{uptake}} = V_{\max} \cdot \frac{[\text{NO}_3^-]}{K_m + [\text{NO}_3^-]} \cdot f(\text{PAR}) \cdot N_{\text{plants}}$
- Alkalinity depletion tracking from upstream nitrification ($7.14\text{ mg CaCO}_3/\text{mg TAN}$)
- Potassium bicarbonate ($\text{KHCO}_3$) and Calcium hydroxide ($\text{Ca(OH)}_2$) buffering dosing
- Prevention of pH crashes ($< 6.4$) and lettuce tip-burn via calcium/potassium supplementation.
"""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class HydroponicSubsystemType(str, Enum):
    DEEP_WATER_CULTURE_DWC = "dwc_raft"
    NUTRIENT_FILM_TECHNIQUE = "nft_channel"
    MEDIA_FILLED_BED = "media_bed"


class AquaponicCropType(str, Enum):
    BUTTERHEAD_LETTUCE = "butterhead_lettuce"
    PAK_CHOI = "pak_choi"
    SWEET_BASIL = "sweet_basil"
    WATER_SPINACH = "water_spinach"


class BaseChemical(str, Enum):
    POTASSIUM_BICARBONATE = "khco3"
    CALCIUM_HYDROXIDE = "ca_oh_2"
    POTASSIUM_SILICATE = "k2sio3"


class HydroponicBedState(BaseModel):
    """Real-time biophysical state of the plant growing component."""
    bed_id: str = "DWC_BED_01"
    subsystem_type: HydroponicSubsystemType = HydroponicSubsystemType.DEEP_WATER_CULTURE_DWC
    crop_type: AquaponicCropType = AquaponicCropType.BUTTERHEAD_LETTUCE
    bed_area_m2: float = Field(40.0, ge=1.0)
    plant_count: int = Field(1000, ge=10)
    water_volume_m3: float = Field(12.0, ge=0.5)
    inlet_no3_mg_l: float = Field(..., ge=0.0)
    outlet_no3_mg_l: float = Field(..., ge=0.0)
    daily_no3_uptake_grams: float = Field(..., ge=0.0)
    alkalinity_mg_l_caco3: float = Field(75.0, ge=0.0)
    ph: float = Field(6.8, ge=5.0, le=9.0)
    is_alkalinity_critical: bool = False
    is_nitrate_deficient: bool = False


class BufferDosingRecommendation(BaseModel):
    """Actionable base dosing prescription to neutralize nitrification acidity."""
    chemical: BaseChemical
    dose_grams: float
    current_alkalinity_mg_l: float
    target_alkalinity_mg_l: float
    expected_alkalinity_after_mg_l: float
    potassium_or_calcium_added_grams: float
    rationale: str


class AquaponicHydroponicsEngine:
    """
    Simulates plant nitrate extraction and buffer dosing for pH stabilization.
    """

    # Target aquaponic alkalinity: 80 - 120 mg/L CaCO3
    TARGET_ALKALINITY_MG_L: ClassVar[float] = 100.0
    CRITICAL_ALKALINITY_MG_L: ClassVar[float] = 50.0

    # Minimum nitrate threshold for leafy greens: ~40 mg/L NO3
    MIN_NITRATE_THRESHOLD_MG_L: ClassVar[float] = 40.0

    # Max uptake rate in grams NO3 per plant per day at full PAR and canopy maturity
    CROP_UPTAKE_PROFILES: ClassVar[dict[AquaponicCropType, dict[str, float]]] = {
        AquaponicCropType.BUTTERHEAD_LETTUCE: {"v_max_g_plant_day": 0.035, "km_mg_l": 15.0, "plants_per_m2": 25.0},
        AquaponicCropType.PAK_CHOI: {"v_max_g_plant_day": 0.045, "km_mg_l": 18.0, "plants_per_m2": 30.0},
        AquaponicCropType.SWEET_BASIL: {"v_max_g_plant_day": 0.030, "km_mg_l": 12.0, "plants_per_m2": 22.0},
        AquaponicCropType.WATER_SPINACH: {"v_max_g_plant_day": 0.055, "km_mg_l": 20.0, "plants_per_m2": 35.0},
    }

    @classmethod
    def calculate_crop_nitrate_uptake(
        cls,
        crop_type: AquaponicCropType,
        plant_count: int,
        no3_concentration_mg_l: float,
        par_umol_m2_s: float = 400.0,
    ) -> float:
        """
        Computes total grams of NO3 assimilated by crop canopy per day.
        Uptake follows Michaelis-Menten kinetics scaled by photosynthetically active radiation (PAR).
        """
        profile = cls.CROP_UPTAKE_PROFILES.get(
            crop_type,
            cls.CROP_UPTAKE_PROFILES[AquaponicCropType.BUTTERHEAD_LETTUCE],
        )

        v_max = profile["v_max_g_plant_day"]
        km = profile["km_mg_l"]

        # Michaelis-Menten substrate factor
        if no3_concentration_mg_l <= 0.0:
            return 0.0
        substrate_factor = no3_concentration_mg_l / (km + no3_concentration_mg_l)

        # PAR factor (400 umol/m2s is ~full greenhouse light; light saturation at ~600)
        par_factor = min(1.0, max(0.2, par_umol_m2_s / 500.0))

        daily_uptake_g = plant_count * v_max * substrate_factor * par_factor
        return round(daily_uptake_g, 2)

    @classmethod
    def calculate_buffer_dosing(
        cls,
        current_alkalinity_mg_l: float,
        water_volume_m3: float,
        target_alkalinity_mg_l: float = 100.0,
        chemical: BaseChemical = BaseChemical.POTASSIUM_BICARBONATE,
    ) -> BufferDosingRecommendation:
        """
        Calculates grams of base chemical required to elevate system alkalinity:
        - KHCO3: 1 g adds ~0.50 g CaCO3 equivalent alkalinity, and adds 0.39 g Potassium (K+).
        - Ca(OH)2: 1 g adds ~1.35 g CaCO3 equivalent alkalinity, and adds 0.54 g Calcium (Ca2+).
        """
        alk_deficit_mg_l = max(0.0, target_alkalinity_mg_l - current_alkalinity_mg_l)
        total_deficit_grams_caco3 = alk_deficit_mg_l * water_volume_m3

        if chemical == BaseChemical.POTASSIUM_BICARBONATE:
            # KHCO3 molecular weight = 100.12 g/mol, adds 1 mol HCO3- = 50 g CaCO3 equiv
            dose_grams = total_deficit_grams_caco3 / 0.50
            nutrient_added_g = dose_grams * 0.39
            nutrient_label = "Potassium (K+)"
        elif chemical == BaseChemical.CALCIUM_HYDROXIDE:
            # Ca(OH)2 adds 2 OH- equivalents
            dose_grams = total_deficit_grams_caco3 / 1.35
            nutrient_added_g = dose_grams * 0.54
            nutrient_label = "Calcium (Ca2+)"
        else:
            dose_grams = total_deficit_grams_caco3 / 0.45
            nutrient_added_g = dose_grams * 0.35
            nutrient_label = "Potassium (K+)"

        dose_grams = round(dose_grams, 1)
        nutrient_added_g = round(nutrient_added_g, 1)

        rationale = (
            f"Dose {dose_grams:.1f} g of {chemical.value.upper()} to restore alkalinity from "
            f"{current_alkalinity_mg_l:.1f} to {target_alkalinity_mg_l:.1f} mg/L CaCO3. "
            f"Supplements {nutrient_added_g:.1f} g of {nutrient_label} for plant nutrition."
        )

        return BufferDosingRecommendation(
            chemical=chemical,
            dose_grams=dose_grams,
            current_alkalinity_mg_l=current_alkalinity_mg_l,
            target_alkalinity_mg_l=target_alkalinity_mg_l,
            expected_alkalinity_after_mg_l=target_alkalinity_mg_l,
            potassium_or_calcium_added_grams=nutrient_added_g,
            rationale=rationale,
        )

    @classmethod
    def simulate_hydroponic_step(
        cls,
        state: HydroponicBedState,
        inlet_no3_mg_l: float,
        water_flow_m3_h: float = 3.5,
        par_umol_m2_s: float = 400.0,
        dt_hours: float = 1.0,
    ) -> HydroponicBedState:
        """
        Advances plant bed state, removing nitrate according to vegetative uptake.
        """
        daily_uptake_g = cls.calculate_crop_nitrate_uptake(
            crop_type=state.crop_type,
            plant_count=state.plant_count,
            no3_concentration_mg_l=inlet_no3_mg_l,
            par_umol_m2_s=par_umol_m2_s,
        )

        step_uptake_g = (daily_uptake_g / 24.0) * dt_hours
        incoming_no3_g = inlet_no3_mg_l * water_flow_m3_h * dt_hours
        absorbed_g = min(incoming_no3_g, step_uptake_g)

        remaining_no3_g = max(0.0, incoming_no3_g - absorbed_g)
        outlet_no3_mg_l = remaining_no3_g / (water_flow_m3_h * dt_hours)

        is_critical_alk = state.alkalinity_mg_l_caco3 < cls.CRITICAL_ALKALINITY_MG_L
        is_deficient_no3 = outlet_no3_mg_l < cls.MIN_NITRATE_THRESHOLD_MG_L

        return HydroponicBedState(
            bed_id=state.bed_id,
            subsystem_type=state.subsystem_type,
            crop_type=state.crop_type,
            bed_area_m2=state.bed_area_m2,
            plant_count=state.plant_count,
            water_volume_m3=state.water_volume_m3,
            inlet_no3_mg_l=round(inlet_no3_mg_l, 2),
            outlet_no3_mg_l=round(outlet_no3_mg_l, 2),
            daily_no3_uptake_grams=round(daily_uptake_g, 2),
            alkalinity_mg_l_caco3=state.alkalinity_mg_l_caco3,
            ph=state.ph,
            is_alkalinity_critical=is_critical_alk,
            is_nitrate_deficient=is_deficient_no3,
        )
