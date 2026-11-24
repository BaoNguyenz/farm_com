"""
Solar Thermal Crop Drying Kinetics & Bioactive Nutrient Retention Engine.

Implements thin-layer moisture transport and quality degradation kinetics for agricultural produce:
- Page (1949) and Midilli-Kucuk empirical thin-layer drying equations.
- Modified Oswin / Henderson equilibrium moisture content (EMC) sorption isotherms.
- Fickian effective moisture diffusivity (D_eff) with Arrhenius temperature dependency.
- Water activity (a_w) and microbiological stability boundary (a_w <= 0.60).
- Thermal degradation kinetics of Ascorbic Acid (Vitamin C) and Anthocyanin pigment retention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class CropDryingCommodity(str, Enum):
    """Agricultural commodities dried in precision solar facilities."""
    STRAWBERRY_SLICES = "strawberry_slices"
    CHERRY_TOMATOES = "cherry_tomatoes"
    ARTICHOKE_HERBAL_TEA = "artichoke_herbal_tea"
    SHIITAKE_MUSHROOMS = "shiitake_mushrooms"
    ARABICA_COFFEE_BEANS = "arabica_coffee_beans"


class DryingQualityGrade(str, Enum):
    """Quality classification of dried produce."""
    GRADE_AAA_PREMIUM = "grade_aaa_premium"
    GRADE_AA_STANDARD = "grade_aa_standard"
    GRADE_B_SUBSTANDARD = "grade_b_substandard"


class CommodityDryingProperties(BaseModel):
    """Biophysical and sorption parameters for a specific crop."""
    commodity: CropDryingCommodity
    initial_moisture_wb_pct: float = Field(..., description="Initial wet-basis moisture % (e.g. 90% for berries)")
    target_moisture_wb_pct: float = Field(..., description="Target dry safe storage moisture % (e.g. 12%)")
    max_safe_temperature_c: float = Field(55.0, description="Thermal threshold before enzyme/vitamin destruction")
    page_k: float = Field(0.045, description="Drying rate constant k in Page model (1/h)")
    page_n: float = Field(1.15, description="Empirical exponent n in Page model")
    oswin_c1: float = Field(0.12, description="Modified Oswin isotherm parameter C1")
    oswin_c2: float = Field(0.38, description="Modified Oswin isotherm parameter C2")
    activation_energy_kj_mol: float = Field(32.5, description="Arrhenius activation energy Ea (kJ/mol)")
    initial_vitamin_c_mg_100g: float = Field(60.0, description="Fresh tissue ascorbic acid concentration")


COMMODITY_CATALOG: dict[CropDryingCommodity, CommodityDryingProperties] = {
    CropDryingCommodity.STRAWBERRY_SLICES: CommodityDryingProperties(
        commodity=CropDryingCommodity.STRAWBERRY_SLICES,
        initial_moisture_wb_pct=90.0,
        target_moisture_wb_pct=12.0,
        max_safe_temperature_c=52.0,
        page_k=0.065,
        page_n=1.18,
        oswin_c1=0.115,
        oswin_c2=0.365,
        activation_energy_kj_mol=31.2,
        initial_vitamin_c_mg_100g=58.8,
    ),
    CropDryingCommodity.CHERRY_TOMATOES: CommodityDryingProperties(
        commodity=CropDryingCommodity.CHERRY_TOMATOES,
        initial_moisture_wb_pct=93.5,
        target_moisture_wb_pct=14.0,
        max_safe_temperature_c=55.0,
        page_k=0.042,
        page_n=1.12,
        oswin_c1=0.128,
        oswin_c2=0.395,
        activation_energy_kj_mol=34.8,
        initial_vitamin_c_mg_100g=26.0,
    ),
    CropDryingCommodity.ARTICHOKE_HERBAL_TEA: CommodityDryingProperties(
        commodity=CropDryingCommodity.ARTICHOKE_HERBAL_TEA,
        initial_moisture_wb_pct=82.0,
        target_moisture_wb_pct=8.5,
        max_safe_temperature_c=60.0,
        page_k=0.095,
        page_n=1.22,
        oswin_c1=0.092,
        oswin_c2=0.310,
        activation_energy_kj_mol=28.5,
        initial_vitamin_c_mg_100g=15.0,
    ),
    CropDryingCommodity.SHIITAKE_MUSHROOMS: CommodityDryingProperties(
        commodity=CropDryingCommodity.SHIITAKE_MUSHROOMS,
        initial_moisture_wb_pct=88.0,
        target_moisture_wb_pct=11.0,
        max_safe_temperature_c=58.0,
        page_k=0.055,
        page_n=1.15,
        oswin_c1=0.105,
        oswin_c2=0.340,
        activation_energy_kj_mol=30.0,
        initial_vitamin_c_mg_100g=18.5,
    ),
    CropDryingCommodity.ARABICA_COFFEE_BEANS: CommodityDryingProperties(
        commodity=CropDryingCommodity.ARABICA_COFFEE_BEANS,
        initial_moisture_wb_pct=52.0,
        target_moisture_wb_pct=11.5,
        max_safe_temperature_c=45.0,
        page_k=0.032,
        page_n=1.05,
        oswin_c1=0.145,
        oswin_c2=0.420,
        activation_energy_kj_mol=36.0,
        initial_vitamin_c_mg_100g=5.0,
    ),
}


class DryingBatchState(BaseModel):
    """Instantaneous state of crop batch inside the drying chamber."""
    commodity: CropDryingCommodity
    elapsed_time_hours: float
    moisture_dry_basis_db: float = Field(..., description="kg water / kg dry matter")
    moisture_wet_basis_pct: float = Field(..., ge=0.0, le=100.0)
    moisture_ratio_mr: float = Field(..., ge=0.0, le=1.0)
    equilibrium_moisture_db: float
    water_activity_aw: float = Field(..., ge=0.0, le=1.0)
    effective_diffusivity_m2_s: float
    vitamin_c_retention_pct: float = Field(..., ge=0.0, le=100.0)
    remaining_vitamin_c_mg_100g: float
    drying_rate_db_per_hour: float
    chamber_air_temp_c: float
    chamber_air_rh_pct: float
    is_drying_completed: bool
    quality_grade: DryingQualityGrade


@dataclass
class SolarDryingKineticsEngine:
    """
    Simulates thin-layer drying curves, moisture diffusion, and nutrient retention.
    """
    UNIVERSAL_GAS_CONSTANT_R: ClassVar[float] = 8.314  # J / (mol * K)
    DIFFUSIVITY_PRE_EXP_D0: ClassVar[float] = 1.25e-4  # m^2 / s

    @staticmethod
    def wet_to_dry_basis(moisture_wb_pct: float) -> float:
        """Converts wet-basis moisture percentage to dry-basis decimal (kg water / kg dry solid)."""
        if moisture_wb_pct >= 100.0:
            raise ValueError("Wet basis moisture cannot be >= 100%")
        wb = max(0.0, moisture_wb_pct / 100.0)
        return round(wb / (1.0 - wb), 4)

    @staticmethod
    def dry_to_wet_basis(moisture_db: float) -> float:
        """Converts dry-basis decimal to wet-basis percentage."""
        if moisture_db < 0:
            raise ValueError("Dry basis moisture cannot be negative")
        wb = moisture_db / (1.0 + moisture_db)
        return round(wb * 100.0, 2)

    @staticmethod
    def calculate_equilibrium_moisture(
        temp_c: float,
        rh_pct: float,
        props: CommodityDryingProperties,
    ) -> float:
        """
        Calculates Equilibrium Moisture Content (EMC, dry basis) via modified Oswin isotherm:
        M_e = (C1 + C2 * T) * (RH / (100 - RH))^C3
        """
        rh_clamped = max(1.0, min(rh_pct, 99.0))
        relative_humidity_ratio = rh_clamped / (100.0 - rh_clamped)
        # Oswin empirical approximation
        me_db = (props.oswin_c1 + 0.0005 * temp_c) * (relative_humidity_ratio ** props.oswin_c2)
        return max(0.02, round(me_db, 4))

    def calculate_effective_diffusivity(
        self,
        temp_c: float,
        props: CommodityDryingProperties,
    ) -> float:
        """
        Calculates Fickian effective moisture diffusivity D_eff (m^2/s) using Arrhenius law:
        D_eff = D0 * exp(-E_a / (R * T_kelvin))
        """
        t_kelvin = temp_c + 273.15
        ea_j_mol = props.activation_energy_kj_mol * 1000.0
        exponent = -ea_j_mol / (self.UNIVERSAL_GAS_CONSTANT_R * t_kelvin)
        d_eff = self.DIFFUSIVITY_PRE_EXP_D0 * math.exp(exponent)
        return round(d_eff, 11)

    @staticmethod
    def calculate_water_activity(moisture_wb_pct: float, target_wb_pct: float) -> float:
        """
        Estimates water activity a_w from tissue moisture.
        Safe microbial storage threshold is a_w <= 0.60.
        """
        if moisture_wb_pct <= target_wb_pct:
            return round(0.40 + 0.18 * (moisture_wb_pct / target_wb_pct), 3)
        excess = (moisture_wb_pct - target_wb_pct) / (100.0 - target_wb_pct)
        aw = 0.58 + 0.40 * (excess ** 0.5)
        return round(min(0.99, max(0.20, aw)), 3)

    def simulate_drying_step(
        self,
        commodity: CropDryingCommodity,
        elapsed_hours: float,
        chamber_air_temp_c: float = 48.0,
        chamber_air_rh_pct: float = 25.0,
        previous_moisture_db: float | None = None,
    ) -> DryingBatchState:
        """
        Simulates thin-layer drying progress over time using the Page model:
        MR = exp(-k * t^n)
        M(t) = M_e + (M_0 - M_e) * MR
        """
        props = COMMODITY_CATALOG.get(commodity, COMMODITY_CATALOG[CropDryingCommodity.STRAWBERRY_SLICES])
        m0_db = self.wet_to_dry_basis(props.initial_moisture_wb_pct)
        me_db = self.calculate_equilibrium_moisture(chamber_air_temp_c, chamber_air_rh_pct, props)

        # Temperature-adjusted Page k factor: k(T) = k_base * exp(0.045 * (T - 40))
        temp_factor = math.exp(0.045 * (chamber_air_temp_c - 40.0))
        adj_k = props.page_k * temp_factor

        # Moisture Ratio from Page equation
        mr = math.exp(-adj_k * (elapsed_hours ** props.page_n))
        mr = max(0.0, min(1.0, mr))

        current_db = me_db + (m0_db - me_db) * mr
        current_wb = self.dry_to_wet_basis(current_db)

        # Diffusivity
        d_eff = self.calculate_effective_diffusivity(chamber_air_temp_c, props)

        # Water activity
        aw = self.calculate_water_activity(current_wb, props.target_moisture_wb_pct)

        # Vitamin C thermal degradation: 1st order k_deg = 0.012 * exp(0.05 * (T - 45))
        k_vit = 0.012 * math.exp(0.055 * max(0.0, chamber_air_temp_c - 45.0))
        vit_c_retention = math.exp(-k_vit * elapsed_hours) * 100.0
        vit_c_retention = max(10.0, min(100.0, vit_c_retention))
        remaining_vit_c = round(props.initial_vitamin_c_mg_100g * (vit_c_retention / 100.0), 1)

        # Drying rate
        prev_db = previous_moisture_db if previous_moisture_db is not None else m0_db
        drying_rate = max(0.0, round((prev_db - current_db), 4))

        is_done = current_wb <= props.target_moisture_wb_pct

        # Quality Grade determination
        if is_done and aw <= 0.60 and vit_c_retention >= 75.0 and chamber_air_temp_c <= props.max_safe_temperature_c:
            grade = DryingQualityGrade.GRADE_AAA_PREMIUM
        elif is_done and aw <= 0.65:
            grade = DryingQualityGrade.GRADE_AA_STANDARD
        else:
            grade = DryingQualityGrade.GRADE_B_SUBSTANDARD

        return DryingBatchState(
            commodity=commodity,
            elapsed_time_hours=round(elapsed_hours, 2),
            moisture_dry_basis_db=round(current_db, 4),
            moisture_wet_basis_pct=current_wb,
            moisture_ratio_mr=round(mr, 4),
            equilibrium_moisture_db=me_db,
            water_activity_aw=aw,
            effective_diffusivity_m2_s=d_eff,
            vitamin_c_retention_pct=round(vit_c_retention, 1),
            remaining_vitamin_c_mg_100g=remaining_vit_c,
            drying_rate_db_per_hour=drying_rate,
            chamber_air_temp_c=chamber_air_temp_c,
            chamber_air_rh_pct=chamber_air_rh_pct,
            is_drying_completed=is_done,
            quality_grade=grade,
        )
