"""
Precision Fertigation & Solute Transport Engine.

Implements multi-channel Venturi injection dynamics, automated EC and pH PID mixing,
1D advection-dispersion solute travel, and leaching fraction calculation (Rhoades 1974)
to safeguard against root zone salinization.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class FertigationRecipe(str, Enum):
    """Calibrated crop fertigation nutrient recipes."""

    VEGETATIVE = "vegetative"      # High N (e.g. leafy greens, early strawberry)
    FLOWERING = "flowering"        # Balanced N:K with elevated P
    FRUITING = "fruiting"          # Elevated K:Ca for sugar brix and fruit firmness
    MAINTENANCE = "maintenance"    # Low strength background nourishment


@dataclass
class DosingChannelStatus:
    """Individual fertilizer stock channel status."""

    channel_name: str
    stock_ec_ms_cm: float
    target_ratio_pct: float
    flow_rate_lph: float


@dataclass
class FertigationMixResult:
    """Mixed irrigation water nutrient state."""

    recipe: FertigationRecipe
    measured_ec_ms_cm: float
    target_ec_ms_cm: float
    ec_deviation: float
    measured_ph: float
    target_ph: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    calcium_ppm: float
    total_water_flow_lph: float
    stock_a_injection_lph: float
    stock_b_injection_lph: float
    acid_c_injection_lph: float
    leaching_fraction_pct: float
    salinity_hazard_warning: bool


@dataclass
class SoluteTransportPoint:
    """1D Soil depth solute concentration point."""

    depth_cm: float
    solute_ec_ms_cm: float
    salt_accumulation_index: float


class FertigationSoluteEngine:
    """Precision fertigation PID dosing and solute transport engine."""

    RECIPE_TARGETS: ClassVar[dict[FertigationRecipe, dict[str, float]]] = {
        FertigationRecipe.VEGETATIVE: {
            "target_ec": 1.80,
            "target_ph": 5.85,
            "n_ppm": 160.0,
            "p_ppm": 45.0,
            "k_ppm": 180.0,
            "ca_ppm": 120.0,
        },
        FertigationRecipe.FLOWERING: {
            "target_ec": 2.10,
            "target_ph": 5.95,
            "n_ppm": 140.0,
            "p_ppm": 65.0,
            "k_ppm": 220.0,
            "ca_ppm": 130.0,
        },
        FertigationRecipe.FRUITING: {
            "target_ec": 2.40,
            "target_ph": 6.05,
            "n_ppm": 150.0,
            "p_ppm": 55.0,
            "k_ppm": 280.0,
            "ca_ppm": 140.0,
        },
        FertigationRecipe.MAINTENANCE: {
            "target_ec": 1.20,
            "target_ph": 6.00,
            "n_ppm": 80.0,
            "p_ppm": 30.0,
            "k_ppm": 100.0,
            "ca_ppm": 80.0,
        },
    }

    def __init__(self) -> None:
        # Stock solutions typical strength (EC in mS/cm)
        self.stock_a_ec = 120.0  # Calcium Nitrate + Iron EDTA
        self.stock_b_ec = 140.0  # Potassium, Phosphate, Magnesium, Micronutrients
        self.raw_water_ec = 0.25  # Groundwater/Rainwater background EC
        self.raw_water_ph = 7.35  # Natural alkaline Dalat water

    def compute_pid_injection_rates(
        self,
        target_recipe: FertigationRecipe,
        irrigation_flow_rate_lph: float,
        measured_ec: float | None = None,
        measured_ph: float | None = None,
    ) -> FertigationMixResult:
        """Compute required Venturi stock dosing rates using closed-loop PID approximation."""
        spec = self.RECIPE_TARGETS[target_recipe]
        target_ec = spec["target_ec"]
        target_ph = spec["target_ph"]

        current_ec = measured_ec if measured_ec is not None else target_ec
        current_ph = measured_ph if measured_ph is not None else target_ph

        # EC dosing ratio (parts per thousand) with closed-loop proportional trimming
        ec_delta = max(0.0, target_ec - self.raw_water_ec)
        ec_error = target_ec - current_ec
        stock_ratio = (ec_delta / ((self.stock_a_ec + self.stock_b_ec) / 2.0)) * (1.0 + 0.1 * ec_error)

        # Proportional dosing with safety limits (max 1.5% stock injection)
        stock_ratio = min(0.015, max(0.001, stock_ratio))
        stock_a_flow = round(irrigation_flow_rate_lph * stock_ratio * 0.52, 3)
        stock_b_flow = round(irrigation_flow_rate_lph * stock_ratio * 0.48, 3)

        # Acid injection to titrate raw water alkalinity down to target pH
        ph_excess = max(0.0, current_ph - target_ph)
        acid_c_flow = round(irrigation_flow_rate_lph * (ph_excess * 0.00035), 3)

        # Solute concentration result
        final_ec = round(self.raw_water_ec + (stock_a_flow * self.stock_a_ec + stock_b_flow * self.stock_b_ec) / max(1.0, irrigation_flow_rate_lph), 2)
        final_ph = round(max(5.5, current_ph - (acid_c_flow / max(0.01, irrigation_flow_rate_lph)) * 3000.0), 2)

        # Leaching Fraction (Rhoades, 1974) LF = ECw / (5 * ECe_threshold - ECw)
        # For strawberries/horticulture, threshold ECe is 2.5 mS/cm
        crop_ece_threshold = 2.5
        denom = 5.0 * crop_ece_threshold - final_ec
        leaching_fraction_pct = round(max(5.0, (final_ec / max(1.0, denom)) * 100.0), 1)

        salinity_hazard = final_ec > 2.8 or leaching_fraction_pct > 25.0

        return FertigationMixResult(
            recipe=target_recipe,
            measured_ec_ms_cm=final_ec,
            target_ec_ms_cm=target_ec,
            ec_deviation=round(final_ec - target_ec, 2),
            measured_ph=final_ph,
            target_ph=target_ph,
            nitrogen_ppm=spec["n_ppm"],
            phosphorus_ppm=spec["p_ppm"],
            potassium_ppm=spec["k_ppm"],
            calcium_ppm=spec["ca_ppm"],
            total_water_flow_lph=irrigation_flow_rate_lph,
            stock_a_injection_lph=stock_a_flow,
            stock_b_injection_lph=stock_b_flow,
            acid_c_injection_lph=acid_c_flow,
            leaching_fraction_pct=leaching_fraction_pct,
            salinity_hazard_warning=salinity_hazard,
        )

    def simulate_1d_solute_transport(
        self,
        surface_ec: float,
        soil_depth_cm: float = 60.0,
        pore_water_velocity_cm_h: float = 2.5,
        elapsed_hours: float = 4.0,
        dispersion_coeff_cm2_h: float = 1.2,
    ) -> list[SoluteTransportPoint]:
        """Simulate 1D vertical solute advection-dispersion profile.

        Analytical Ogden-Crank error function solution for 1D step input:
        C(z, t) / C0 = 0.5 * erfc((z - v*t) / (2 * sqrt(D * t)))
        """
        points: list[SoluteTransportPoint] = []
        depth_steps = [0.0, 10.0, 20.0, 30.0, 45.0, 60.0]

        vt = pore_water_velocity_cm_h * elapsed_hours
        sqrt_dt = 2.0 * math.sqrt(max(0.01, dispersion_coeff_cm2_h * elapsed_hours))

        for z in depth_steps:
            arg = (z - vt) / sqrt_dt
            # erfc approximation using math.erfc
            relative_conc = 0.5 * math.erfc(arg)
            ec_at_depth = round(self.raw_water_ec + (surface_ec - self.raw_water_ec) * relative_conc, 2)
            salt_index = round(ec_at_depth / 2.0, 2)

            points.append(
                SoluteTransportPoint(
                    depth_cm=z,
                    solute_ec_ms_cm=ec_at_depth,
                    salt_accumulation_index=salt_index,
                )
            )

        return points
