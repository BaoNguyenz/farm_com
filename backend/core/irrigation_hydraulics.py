"""
Subsurface Drip Irrigation (SDI) & Unsaturated Soil Hydraulics Engine.

Implements the Van Genuchten (1980) soil water retention curve and Mualem (1976)
unsaturated hydraulic conductivity functions to model matric potential, effective
saturation, and subsurface wetted bulb dynamics under buried drip emitters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class SoilTextureClass(str, Enum):
    """USDA soil textural classifications common in Dalat and Central Highlands."""

    SANDY_LOAM = "sandy_loam"  # High infiltration, fast drainage
    LOAM = "loam"              # Balanced retention, optimal horticulture
    BASALT_CLAY = "basalt_clay"  # Dalat basaltic red soil, high retention, slow percolation


@dataclass(frozen=True)
class VanGenuchtenParams:
    """Van Genuchten (1980) hydraulic retention parameters.

    theta_r: Residual water content (cm^3/cm^3)
    theta_s: Saturated water content (porosity) (cm^3/cm^3)
    alpha: Inverse of the air-entry suction value (1/cm)
    n: Pore-size distribution index (dimensionless, n > 1)
    k_sat: Saturated hydraulic conductivity (cm/hour)
    l_param: Pore connectivity parameter (typically 0.5)
    """

    theta_r: float
    theta_s: float
    alpha: float
    n: float
    k_sat: float
    l_param: float = 0.5

    @property
    def m(self) -> float:
        """Mualem condition parameter m = 1 - 1/n."""
        return 1.0 - (1.0 / self.n)


# Calibrated USDA / Dalat Basaltic Soil Catalog
SOIL_HYDRAULIC_CATALOG: dict[SoilTextureClass, VanGenuchtenParams] = {
    SoilTextureClass.SANDY_LOAM: VanGenuchtenParams(
        theta_r=0.065,
        theta_s=0.410,
        alpha=0.075,
        n=1.89,
        k_sat=4.42,  # cm/h
        l_param=0.5,
    ),
    SoilTextureClass.LOAM: VanGenuchtenParams(
        theta_r=0.078,
        theta_s=0.430,
        alpha=0.036,
        n=1.56,
        k_sat=1.04,  # cm/h
        l_param=0.5,
    ),
    SoilTextureClass.BASALT_CLAY: VanGenuchtenParams(
        theta_r=0.102,
        theta_s=0.510,
        alpha=0.018,
        n=1.32,
        k_sat=0.45,  # cm/h
        l_param=0.5,
    ),
}


@dataclass
class WettedBulbGeometry:
    """Subsurface drip emitter wetted bulb dimensional state."""

    depth_cm: float
    radial_width_cm: float
    vertical_height_cm: float
    wetted_volume_liters: float
    capillary_to_gravity_ratio: float
    matric_suction_kpa: float
    effective_saturation: float
    deep_percolation_loss_pct: float


class UnsaturatedHydraulicsEngine:
    """Engine computing unsaturated hydraulic flow, retention curves and wetted bulbs."""

    def __init__(self, soil_type: SoilTextureClass = SoilTextureClass.LOAM) -> None:
        self.soil_type = soil_type
        self.params = SOIL_HYDRAULIC_CATALOG[soil_type]

    def compute_effective_saturation(self, volumetric_water_content: float) -> float:
        """Compute effective saturation Se = (theta - theta_r) / (theta_s - theta_r)."""
        theta = max(self.params.theta_r, min(volumetric_water_content, self.params.theta_s))
        return (theta - self.params.theta_r) / (self.params.theta_s - self.params.theta_r)

    def matric_suction_from_water_content(self, theta: float) -> float:
        """Compute matric pressure head |h| in cm, then convert to suction in kPa.

        Formula: |h| = (1 / alpha) * (Se^(-1/m) - 1)^(1/n)
        1 cm H2O ≈ 0.0980665 kPa.
        """
        se = self.compute_effective_saturation(theta)
        if se <= 0.001:
            return 1500.0  # Wilting point limit in kPa
        if se >= 0.999:
            return 0.1  # Saturated condition, near zero suction

        m = self.params.m
        term = math.pow(se, -1.0 / m) - 1.0
        h_cm = (1.0 / self.params.alpha) * math.pow(max(0.0, term), 1.0 / self.params.n)
        return round(h_cm * 0.0980665, 2)

    def water_content_from_suction(self, matric_suction_kpa: float) -> float:
        """Compute volumetric water content theta from matric suction head in kPa.

        Formula: theta(h) = theta_r + (theta_s - theta_r) / [1 + (alpha * |h|)^n]^m
        """
        if matric_suction_kpa <= 0.0:
            return self.params.theta_s

        h_cm = matric_suction_kpa / 0.0980665
        denom = math.pow(1.0 + math.pow(self.params.alpha * h_cm, self.params.n), self.params.m)
        theta = self.params.theta_r + (self.params.theta_s - self.params.theta_r) / denom
        return round(theta, 4)

    def unsaturated_hydraulic_conductivity(self, theta: float) -> float:
        """Compute Mualem unsaturated hydraulic conductivity K(theta) in cm/hour."""
        se = self.compute_effective_saturation(theta)
        if se <= 0.0:
            return 0.0
        if se >= 1.0:
            return self.params.k_sat

        m = self.params.m
        bracket = 1.0 - math.pow(1.0 - math.pow(se, 1.0 / m), m)
        k = self.params.k_sat * math.pow(se, self.params.l_param) * math.pow(bracket, 2.0)
        return round(k, 5)

    def simulate_subsurface_wetted_bulb(
        self,
        emitter_depth_cm: float,
        emitter_discharge_lph: float,
        application_duration_hours: float,
        initial_volumetric_moisture: float,
    ) -> WettedBulbGeometry:
        """Simulate geometry and water distribution of subsurface drip wetted bulb.

        emitter_depth_cm: Buried emitter depth (e.g., 20.0 cm below surface)
        emitter_discharge_lph: Emitter flow rate in L/h (e.g., 1.6 L/h or 2.2 L/h)
        application_duration_hours: Pumping run time in hours
        """
        total_volume_liters = emitter_discharge_lph * application_duration_hours
        se_init = self.compute_effective_saturation(initial_volumetric_moisture)

        # Capillary vs Gravity ratio: higher in clay, lower in sandy loam
        capillary_gravity_ratio = (self.params.alpha * 100.0) / (self.params.k_sat + 0.1)
        capillary_gravity_ratio = round(max(0.4, min(3.2, capillary_gravity_ratio)), 2)

        # Bulb dimensions (Schwartzman & Zur, 1986 empirical semi-analytical wetted bulb)
        # Radial horizontal width (cm)
        radial_width = 1.32 * math.pow(total_volume_liters, 0.33) * math.pow(self.params.k_sat / emitter_discharge_lph, -0.17) * 20.0
        radial_width = round(max(15.0, min(80.0, radial_width)), 1)

        # Vertical wetted height (cm)
        vertical_height = 0.90 * math.pow(total_volume_liters, 0.38) * math.pow(self.params.k_sat / emitter_discharge_lph, 0.22) * 25.0
        vertical_height = round(max(15.0, min(95.0, vertical_height)), 1)

        # Approximated prolate spheroid volume V = (4/3) * pi * (w/2)^2 * (h/2) in cm3 -> Liters
        bulb_vol_cm3 = (4.0 / 3.0) * math.pi * math.pow(radial_width / 2.0, 2) * (vertical_height / 2.0)
        wetted_volume_liters = round(bulb_vol_cm3 / 1000.0, 1)

        # Final average moisture in bulb
        moisture_gain = total_volume_liters / max(1.0, wetted_volume_liters)
        final_moisture = min(self.params.theta_s, initial_volumetric_moisture + moisture_gain * 0.45)
        suction_kpa = self.matric_suction_from_water_content(final_moisture)
        se_final = self.compute_effective_saturation(final_moisture)

        # Deep percolation: occurs if bottom of bulb extends beyond root zone (typically > 65 cm)
        bulb_bottom_depth = emitter_depth_cm + (vertical_height / 2.0)
        deep_percolation_loss_pct = 0.0
        if bulb_bottom_depth > 60.0:
            excess_cm = bulb_bottom_depth - 60.0
            deep_percolation_loss_pct = round(min(35.0, excess_cm * 1.5 * (1.0 - se_init * 0.3)), 1)

        return WettedBulbGeometry(
            depth_cm=emitter_depth_cm,
            radial_width_cm=radial_width,
            vertical_height_cm=vertical_height,
            wetted_volume_liters=wetted_volume_liters,
            capillary_to_gravity_ratio=capillary_gravity_ratio,
            matric_suction_kpa=suction_kpa,
            effective_saturation=round(se_final, 3),
            deep_percolation_loss_pct=deep_percolation_loss_pct,
        )
