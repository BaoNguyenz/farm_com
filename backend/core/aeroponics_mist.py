"""
Vertical Aeroponics Ultrasonic Root-Zone Misting & Nutrient Uptake Kinetics Engine.

Models precision soilless aeroponic root chambers:
- Ultrasonic piezo-transducer atomization (5-50 um Sauter Mean Diameter D32 droplets).
- Dissolved Oxygen (DO) saturation in root-zone mist film via temperature-dependent solubility.
- Michaelis-Menten active ion uptake kinetics for Nitrate (NO3-) and Potassium (K+).
- Adaptive misting duty-cycle scheduling (ON/OFF seconds) driven by root-chamber VPD.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel


class AtomizerMode(str, Enum):
    """Aeroponic mist generation technology."""
    ULTRASONIC_PIEZO_1_7MHZ = "ultrasonic_piezo_1_7mhz"  # ~15 um fine fog
    HIGH_PRESSURE_NOZZLE_80PSI = "high_pressure_nozzle_80psi"  # ~45 um mist


class AeroponicChamberState(BaseModel):
    """Instantaneous biophysical and hydraulic telemetry of an aeroponic tower."""
    atomizer_mode: AtomizerMode
    root_chamber_temp_c: float
    root_chamber_rh_pct: float
    droplet_sauter_diameter_um: float
    dissolved_oxygen_mg_l: float
    nitrate_uptake_mg_h_per_plant: float
    potassium_uptake_mg_h_per_plant: float
    mist_on_seconds: int
    mist_off_seconds: int
    water_savings_vs_soil_pct: float = 95.0
    root_desiccation_risk: bool
    chamber_status: str


@dataclass
class AeroponicsMistEngine:
    """
    Simulates ultrasonic misting thermodynamics, oxygen transfer, and root ion uptake.
    """
    NO3_VMAX_MG_H: ClassVar[float] = 18.5
    NO3_KM_PPM: ClassVar[float] = 35.0
    K_VMAX_MG_H: ClassVar[float] = 22.0
    K_KM_PPM: ClassVar[float] = 42.0

    @staticmethod
    def compute_droplet_diameter_um(mode: AtomizerMode, piezo_freq_mhz: float = 1.7) -> float:
        """
        Calculates Sauter Mean Diameter (D32) of aerosolized nutrient droplets.
        Lang's capillary wave equation scaling for ultrasonic atomization.
        """
        if mode == AtomizerMode.ULTRASONIC_PIEZO_1_7MHZ:
            # D32 inversely proportional to f^(2/3), ~15 um at 1.7 MHz
            return round(21.4 / (max(0.5, piezo_freq_mhz) ** (2.0 / 3.0)), 1)
        return 45.0

    @staticmethod
    def compute_mist_dissolved_oxygen(temp_c: float) -> float:
        """
        Computes saturated Dissolved Oxygen (mg/L) in micro-droplet film:
        DO_sat ~ 14.62 - 0.3898*T + 0.006969*T^2 - 5.897e-5*T^3
        """
        t = max(5.0, min(40.0, temp_c))
        do_sat = 14.62 - 0.3898 * t + 0.006969 * (t**2) - 5.897e-5 * (t**3)
        return round(do_sat, 2)

    def compute_michaelis_menten_uptake(
        self,
        nitrate_ppm: float,
        potassium_ppm: float,
        root_temp_c: float,
    ) -> tuple[float, float]:
        """
        Calculates active root ion absorption (mg/hour/plant) with Q10 temperature scaling.
        """
        # Optimal root uptake around 21°C; drops if too cold or hypoxic (>26°C)
        temp_factor = math.exp(-0.02 * ((root_temp_c - 21.0) ** 2))
        no3_uptake = (self.NO3_VMAX_MG_H * nitrate_ppm / (self.NO3_KM_PPM + nitrate_ppm)) * temp_factor
        k_uptake = (self.K_VMAX_MG_H * potassium_ppm / (self.K_KM_PPM + potassium_ppm)) * temp_factor
        return round(no3_uptake, 2), round(k_uptake, 2)

    def evaluate_chamber(
        self,
        atomizer_mode: AtomizerMode = AtomizerMode.ULTRASONIC_PIEZO_1_7MHZ,
        root_chamber_temp_c: float = 21.0,
        root_chamber_rh_pct: float = 92.0,
        nitrate_ppm: float = 140.0,
        potassium_ppm: float = 180.0,
    ) -> AeroponicChamberState:
        """Evaluates misting duty cycle, droplet oxygenation, and root health."""
        d32 = self.compute_droplet_diameter_um(atomizer_mode)
        do_mg_l = self.compute_mist_dissolved_oxygen(root_chamber_temp_c)
        no3_rate, k_rate = self.compute_michaelis_menten_uptake(nitrate_ppm, potassium_ppm, root_chamber_temp_c)

        # Adaptive duty cycle: drier/warmer chamber requires shorter OFF interval
        if root_chamber_rh_pct < 85.0 or root_chamber_temp_c > 25.0:
            on_s, off_s = 15, 90
        elif root_chamber_rh_pct < 92.0:
            on_s, off_s = 10, 150
        else:
            on_s, off_s = 8, 240

        desiccation_risk = root_chamber_rh_pct < 80.0
        if desiccation_risk:
            status = "CRITICAL_ROOT_DESICCATION_RISK"
        elif root_chamber_temp_c > 26.0:
            status = "WARNING_ROOT_HYPOXIA_HEAT"
        else:
            status = "OPTIMAL_ULTRASONIC_MIST"

        return AeroponicChamberState(
            atomizer_mode=atomizer_mode,
            root_chamber_temp_c=root_chamber_temp_c,
            root_chamber_rh_pct=root_chamber_rh_pct,
            droplet_sauter_diameter_um=d32,
            dissolved_oxygen_mg_l=do_mg_l,
            nitrate_uptake_mg_h_per_plant=no3_rate,
            potassium_uptake_mg_h_per_plant=k_rate,
            mist_on_seconds=on_s,
            mist_off_seconds=off_s,
            root_desiccation_risk=desiccation_risk,
            chamber_status=status,
        )
