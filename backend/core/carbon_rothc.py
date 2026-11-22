"""
RothC-26.3 Soil Organic Carbon (SOC) Turnover Kinetics & Biochar Persistence Engine.

Implements the standard Rothamsted Carbon Model (RothC) for agricultural soils:
- 5 Compartments: Decomposable Plant Material (DPM), Resistant Plant Material (RPM),
  Microbial Biomass (BIO), Humified Organic Matter (HUM), and Inert Organic Matter (IOM).
- Environmental rate modifiers: Temperature response a(T), Soil Moisture Deficit b(M),
  and Vegetative Canopy Soil Cover factor c.
- Clay content protection kinetics: adjusts the microbial efficiency ratio of CO2 respiration
  versus BIO + HUM synthesis.
- Biochar recalcitrance modeling: pyrolyzed stable carbon with inert fraction >= 95% and
  centennial half-life.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

from pydantic import BaseModel, Field


class RothCPools(BaseModel):
    """Soil Organic Carbon stocks partitioned across 5 RothC pools (tonnes C/ha)."""
    dpm: float = Field(0.8, ge=0.0, description="Decomposable Plant Material (t C/ha)")
    rpm: float = Field(3.5, ge=0.0, description="Resistant Plant Material (t C/ha)")
    bio: float = Field(1.2, ge=0.0, description="Microbial Biomass (t C/ha)")
    hum: float = Field(22.5, ge=0.0, description="Humified Organic Matter (t C/ha)")
    iom: float = Field(4.0, ge=0.0, description="Inert Organic Matter (t C/ha)")

    @property
    def total_soc(self) -> float:
        """Total Soil Organic Carbon in tonnes Carbon per hectare."""
        return round(self.dpm + self.rpm + self.bio + self.hum + self.iom, 3)

    @property
    def active_soc(self) -> float:
        """Dynamic non-inert pools subject to biological turnover."""
        return round(self.dpm + self.rpm + self.bio + self.hum, 3)


class CarbonAmendment(BaseModel):
    """Organic matter input to topsoil (crop residue, compost, or biochar)."""
    amendment_type: str = Field("crop_residue", description="crop_residue, farmyard_compost, digestate, or biochar")
    carbon_input_t_c_per_ha: float = Field(..., ge=0.0, description="Total carbon applied (t C/ha)")
    dpm_rpm_ratio: float = Field(1.44, ge=0.0, description="Ratio of DPM to RPM for plant inputs")
    inert_biochar_fraction: float = Field(0.0, ge=0.0, le=1.0, description="Fraction allocated to stable IOM pool")


class EnvironmentalModifiers(BaseModel):
    """Dimensionless environmental rate modifiers for RothC biological decomposition."""
    temperature_modifier_a: float = Field(..., ge=0.0)
    moisture_modifier_b: float = Field(..., ge=0.0, le=1.0)
    cover_modifier_c: float = Field(..., ge=0.0, le=1.0)
    net_rate_modifier_xi: float = Field(..., ge=0.0)
    clay_respiration_ratio_x: float = Field(..., ge=0.0)
    fraction_co2_respired: float = Field(..., ge=0.0, le=1.0)


class RothCSimulationStep(BaseModel):
    """Monthly or sub-annual simulation step for soil organic carbon stocks."""
    step_month: int
    ambient_temp_c: float
    soil_moisture_deficit_mm: float
    vegetated_cover: bool
    carbon_input_t_c_ha: float
    pools_before: RothCPools
    pools_after: RothCPools
    co2_emitted_t_co2_ha: float
    net_soc_change_t_c_ha: float
    modifiers: EnvironmentalModifiers


@dataclass
class RothCKineticsEngine:
    """
    Rothamsted Carbon Model (RothC-26.3) computation engine.
    Standard turnover decomposition rate constants (year^-1):
    DPM: 10.0, RPM: 0.30, BIO: 0.66, HUM: 0.02, IOM: 0.00
    """
    K_DPM: ClassVar[float] = 10.0
    K_RPM: ClassVar[float] = 0.30
    K_BIO: ClassVar[float] = 0.66
    K_HUM: ClassVar[float] = 0.02
    K_IOM: ClassVar[float] = 0.00

    CLAY_PCT: ClassVar[float] = 32.0  # Dalat volcanic basaltic clay content ~32%
    MAX_SMD_MM: ClassVar[float] = 50.0  # Topsoil maximum moisture deficit in mm

    def compute_temperature_modifier(self, temp_c: float) -> float:
        """
        RothC temperature rate modifier a(T):
        a(T) = 47.9 / (1 + exp(106 / (T + 18.3)))
        """
        if temp_c <= -18.0:
            return 0.0
        val = 47.9 / (1.0 + math.exp(106.0 / (temp_c + 18.3)))
        return round(val, 3)

    def compute_moisture_modifier(self, smd_mm: float, max_smd_mm: float | None = None) -> float:
        """
        RothC soil moisture deficit rate modifier b(M):
        b(M) = max(0.2, 1.0 - 0.8 * (SMD / SMD_max))
        """
        limit = max_smd_mm or self.MAX_SMD_MM
        clamped_smd = max(0.0, min(smd_mm, limit))
        b = 1.0 - 0.8 * (clamped_smd / limit)
        return round(max(0.2, b), 3)

    @staticmethod
    def compute_cover_modifier(vegetated: bool) -> float:
        """Vegetated canopy reduces surface evaporation and soil exposure (1.0 covered, 0.6 bare)."""
        return 1.0 if vegetated else 0.6

    def compute_clay_partitioning(self, clay_pct: float | None = None) -> tuple[float, float, float, float]:
        """
        Calculates microbial partitioning into CO2 vs (BIO + HUM) based on clay content:
        x = 1.67 * (1.85 + 1.60 * exp(-0.0786 * %clay))
        CO2 fraction = x / (x + 1)
        BIO fraction = 0.46 * (1 - CO2 fraction)
        HUM fraction = 0.54 * (1 - CO2 fraction)
        """
        clay = clay_pct if clay_pct is not None else self.CLAY_PCT
        x = 1.67 * (1.85 + 1.60 * math.exp(-0.0786 * clay))
        frac_co2 = x / (x + 1.0)
        frac_bio = 0.46 * (1.0 - frac_co2)
        frac_hum = 0.54 * (1.0 - frac_co2)
        return round(x, 3), round(frac_co2, 3), round(frac_bio, 3), round(frac_hum, 3)

    def step_month(
        self,
        pools: RothCPools,
        temp_c: float = 20.0,
        smd_mm: float = 15.0,
        vegetated: bool = True,
        amendment: CarbonAmendment | None = None,
        dt_years: float = 1.0 / 12.0,  # 1 month
        clay_pct: float | None = None,
    ) -> RothCSimulationStep:
        """
        Advances the 5-pool RothC state by dt_years (e.g. 1 month).
        """
        a = self.compute_temperature_modifier(temp_c)
        b = self.compute_moisture_modifier(smd_mm)
        c = self.compute_cover_modifier(vegetated)
        xi = a * b * c

        x_clay, f_co2, f_bio, f_hum = self.compute_clay_partitioning(clay_pct)

        # Decomposition of each pool over dt: delta = S * (1 - exp(-k * xi * dt))
        d_dpm = pools.dpm * (1.0 - math.exp(-self.K_DPM * xi * dt_years))
        d_rpm = pools.rpm * (1.0 - math.exp(-self.K_RPM * xi * dt_years))
        d_bio = pools.bio * (1.0 - math.exp(-self.K_BIO * xi * dt_years))
        d_hum = pools.hum * (1.0 - math.exp(-self.K_HUM * xi * dt_years))

        # Products formed from decomposition
        total_decomposed = d_dpm + d_rpm + d_bio + d_hum
        co2_c_emitted = total_decomposed * f_co2
        new_bio = total_decomposed * f_bio
        new_hum = total_decomposed * f_hum

        # Remaining carbon after decay
        rem_dpm = pools.dpm - d_dpm
        rem_rpm = pools.rpm - d_rpm
        rem_bio = pools.bio - d_bio
        rem_hum = pools.hum - d_hum
        rem_iom = pools.iom

        # Add organic amendment if supplied
        add_dpm = 0.0
        add_rpm = 0.0
        add_iom = 0.0
        add_hum = 0.0
        c_input = 0.0

        if amendment and amendment.carbon_input_t_c_per_ha > 0:
            c_input = amendment.carbon_input_t_c_per_ha
            if amendment.amendment_type == "biochar":
                # High-stability biochar: inert_biochar_fraction (e.g. 95%) goes to stable IOM
                inert_frac = amendment.inert_biochar_fraction or 0.95
                add_iom = c_input * inert_frac
                # Remaining labile biochar fraction enters slow humified pool
                add_hum = c_input * (1.0 - inert_frac)
            elif amendment.amendment_type in ("farmyard_compost", "digestate"):
                # Digestate/compost: high HUM fraction, lower DPM
                add_hum = c_input * 0.45
                remaining_c = c_input * 0.55
                add_dpm = remaining_c * (amendment.dpm_rpm_ratio / (amendment.dpm_rpm_ratio + 1.0))
                add_rpm = remaining_c / (amendment.dpm_rpm_ratio + 1.0)
            else:
                # Fresh crop residue
                ratio = amendment.dpm_rpm_ratio
                add_dpm = c_input * (ratio / (ratio + 1.0))
                add_rpm = c_input / (ratio + 1.0)

        # Assemble new pool stocks
        new_pools = RothCPools(
            dpm=round(rem_dpm + add_dpm, 3),
            rpm=round(rem_rpm + add_rpm, 3),
            bio=round(rem_bio + new_bio, 3),
            hum=round(rem_hum + new_hum + add_hum, 3),
            iom=round(rem_iom + add_iom, 3),
        )

        net_change = round(new_pools.total_soc - pools.total_soc, 3)
        # 1 t C emitted = 44 / 12 t CO2 = 3.667 t CO2
        co2_emitted_t_co2 = round(co2_c_emitted * (44.0 / 12.0), 3)

        modifiers = EnvironmentalModifiers(
            temperature_modifier_a=a,
            moisture_modifier_b=b,
            cover_modifier_c=c,
            net_rate_modifier_xi=round(xi, 3),
            clay_respiration_ratio_x=x_clay,
            fraction_co2_respired=f_co2,
        )

        return RothCSimulationStep(
            step_month=1,
            ambient_temp_c=temp_c,
            soil_moisture_deficit_mm=smd_mm,
            vegetated_cover=vegetated,
            carbon_input_t_c_ha=c_input,
            pools_before=pools,
            pools_after=new_pools,
            co2_emitted_t_co2_ha=co2_emitted_t_co2,
            net_soc_change_t_c_ha=net_change,
            modifiers=modifiers,
        )
