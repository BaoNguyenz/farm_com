"""
Post-Harvest Fruit Respiration Kinetics & Transpirational Weight Loss Engine.

Models enzyme-kinetic fruit respiration (Michaelis-Menten with non-competitive CO2 inhibition,
Arrhenius/Q10 temperature sensitivity), fermentative threshold under hypoxia, transpirational
moisture loss, and remaining marketable shelf life for high-value horticultural commodities.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class PerishableCommodity(str, Enum):
    """High-value export produce categories."""

    STRAWBERRIES = "strawberries"      # Extremely perishable, high respiration, Q10 ~ 2.4
    CHERRY_TOMATOES = "cherry_tomatoes" # Climacteric, moderate respiration
    BUTTERHEAD_LETTUCE = "butterhead_lettuce" # High surface area, rapid transpiration loss
    BELL_PEPPER = "bell_pepper"        # Sensitive to chilling injury < 7C


@dataclass(frozen=True)
class CommodityRespirationParams:
    """Biochemical and physical parameters for commodity post-harvest kinetics."""

    v_max_o2_at_20c_ml_kg_h: float  # Maximum O2 consumption rate at 20C
    q10_factor: float               # Temperature sensitivity multiplier per 10C rise
    km_o2_pct: float                # Michaelis constant for O2 (vol %)
    ki_co2_pct: float               # Inhibition constant for CO2 (vol %)
    optimal_storage_temp_c: float   # Recommended cold-room setpoint
    chilling_injury_temp_c: float   # Minimum threshold before cellular damage
    base_shelf_life_days_at_opt: float # Shelf-life at optimal storage
    surface_area_cm2_per_kg: float  # Specific surface area
    skin_perm_g_cm2_h_kpa: float    # Transpirational water vapor permeance


COMMODITY_CATALOG: dict[PerishableCommodity, CommodityRespirationParams] = {
    PerishableCommodity.STRAWBERRIES: CommodityRespirationParams(
        v_max_o2_at_20c_ml_kg_h=45.0,
        q10_factor=2.45,
        km_o2_pct=1.2,
        ki_co2_pct=14.0,
        optimal_storage_temp_c=1.5,
        chilling_injury_temp_c=0.0,
        base_shelf_life_days_at_opt=14.0,
        surface_area_cm2_per_kg=620.0,
        skin_perm_g_cm2_h_kpa=0.0038,
    ),
    PerishableCommodity.CHERRY_TOMATOES: CommodityRespirationParams(
        v_max_o2_at_20c_ml_kg_h=22.0,
        q10_factor=2.15,
        km_o2_pct=0.8,
        ki_co2_pct=18.0,
        optimal_storage_temp_c=10.0,
        chilling_injury_temp_c=8.0,  # Sensitive to low temp pit damage
        base_shelf_life_days_at_opt=21.0,
        surface_area_cm2_per_kg=480.0,
        skin_perm_g_cm2_h_kpa=0.0019,
    ),
    PerishableCommodity.BUTTERHEAD_LETTUCE: CommodityRespirationParams(
        v_max_o2_at_20c_ml_kg_h=38.0,
        q10_factor=2.30,
        km_o2_pct=1.5,
        ki_co2_pct=10.0,
        optimal_storage_temp_c=2.0,
        chilling_injury_temp_c=0.0,
        base_shelf_life_days_at_opt=18.0,
        surface_area_cm2_per_kg=1450.0,
        skin_perm_g_cm2_h_kpa=0.0065,
    ),
    PerishableCommodity.BELL_PEPPER: CommodityRespirationParams(
        v_max_o2_at_20c_ml_kg_h=18.0,
        q10_factor=2.05,
        km_o2_pct=1.0,
        ki_co2_pct=16.0,
        optimal_storage_temp_c=7.5,
        chilling_injury_temp_c=7.0,
        base_shelf_life_days_at_opt=24.0,
        surface_area_cm2_per_kg=320.0,
        skin_perm_g_cm2_h_kpa=0.0015,
    ),
}


@dataclass
class RespirationKineticsResult:
    """State of respiratory metabolism and shelf-life depletion."""

    commodity: PerishableCommodity
    storage_temp_c: float
    ambient_rh_pct: float
    o2_pct: float
    co2_pct: float
    r_o2_ml_kg_h: float
    r_co2_ml_kg_h: float
    respiratory_quotient: float
    daily_heat_generation_kj_kg: float
    hourly_weight_loss_pct: float
    remaining_shelf_life_days: float
    anaerobic_fermentation_risk: bool
    chilling_injury_risk: bool
    freshness_index_score: float  # 0.0 to 100.0


class PostHarvestRespirationEngine:
    """Calculates respiration rate, water loss, and quality decay of harvested crops."""

    def __init__(self, commodity: PerishableCommodity = PerishableCommodity.STRAWBERRIES) -> None:
        self.commodity = commodity
        self.params = COMMODITY_CATALOG[commodity]

    def _saturation_vapor_pressure_kpa(self, temp_c: float) -> float:
        """Tetens formula for saturation water vapor pressure in kPa."""
        return 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))

    def evaluate_respiration(
        self,
        storage_temp_c: float,
        ambient_rh_pct: float = 90.0,
        o2_pct: float = 20.9,
        co2_pct: float = 0.04,
        elapsed_days_in_store: float = 1.0,
    ) -> RespirationKineticsResult:
        """Evaluate Michaelis-Menten respiration kinetics and transpirational decay."""
        # 1. Temperature scaling of V_max via Q10
        q10_exponent = (storage_temp_c - 20.0) / 10.0
        v_max_t = self.params.v_max_o2_at_20c_ml_kg_h * math.pow(self.params.q10_factor, q10_exponent)

        # 2. Gas concentration inhibition: non-competitive CO2 inhibition
        co2_inhibition_factor = 1.0 + (co2_pct / max(0.1, self.params.ki_co2_pct))
        denom = self.params.km_o2_pct + o2_pct * co2_inhibition_factor
        r_o2 = (v_max_t * o2_pct) / max(0.01, denom)
        r_o2 = round(max(0.5, r_o2), 2)

        # 3. Fermentation threshold & Respiratory Quotient (RQ)
        # Standard aerobic RQ is ~1.1; under hypoxia (O2 < 1.5%), RQ jumps up to > 2.5
        is_anaerobic = o2_pct < 1.5
        if is_anaerobic:
            rq = round(1.1 + (1.5 - o2_pct) * 2.2, 2)
        else:
            rq = 1.08

        r_co2 = round(r_o2 * rq, 2)

        # 4. Metabolic heat release (kJ per kg per day)
        # Combustion of glucose: ~0.0207 kJ per ml O2 consumed
        daily_heat_kj_kg = round(r_o2 * 24.0 * 0.0207, 1)

        # 5. Transpirational moisture loss (% per hour)
        # Driving force: VPD between saturated internal fruit pore and surrounding air
        p_sat = self._saturation_vapor_pressure_kpa(storage_temp_c)
        p_air = p_sat * (ambient_rh_pct / 100.0)
        vpd_kpa = max(0.0, p_sat - p_air)

        # Grams water lost per kg fruit per hour = SkinPerm * SurfaceArea * VPD
        water_loss_g_h = self.params.skin_perm_g_cm2_h_kpa * self.params.surface_area_cm2_per_kg * vpd_kpa
        hourly_loss_pct = round((water_loss_g_h / 1000.0) * 100.0, 4)

        # 6. Remaining marketable shelf-life
        # Temperature abuse accelerates senescence: decay factor kd ≈ 0.12 per degree C above optimal
        temp_delta = max(0.0, storage_temp_c - self.params.optimal_storage_temp_c)
        decay_factor = math.exp(-0.11 * temp_delta)
        depleted_shelf_life = max(0.0, self.params.base_shelf_life_days_at_opt * decay_factor - elapsed_days_in_store)
        remaining_days = round(depleted_shelf_life, 1)

        # 7. Quality & freshness index (0 to 100)
        freshness_score = round(max(0.0, min(100.0, (remaining_days / self.params.base_shelf_life_days_at_opt) * 100.0)), 1)
        chilling_risk = storage_temp_c < self.params.chilling_injury_temp_c

        return RespirationKineticsResult(
            commodity=self.commodity,
            storage_temp_c=storage_temp_c,
            ambient_rh_pct=ambient_rh_pct,
            o2_pct=o2_pct,
            co2_pct=co2_pct,
            r_o2_ml_kg_h=r_o2,
            r_co2_ml_kg_h=r_co2,
            respiratory_quotient=rq,
            daily_heat_generation_kj_kg=daily_heat_kj_kg,
            hourly_weight_loss_pct=hourly_loss_pct,
            remaining_shelf_life_days=remaining_days,
            anaerobic_fermentation_risk=is_anaerobic,
            chilling_injury_risk=chilling_risk,
            freshness_index_score=freshness_score,
        )
