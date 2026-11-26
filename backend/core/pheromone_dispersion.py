"""
Atmospheric Pheromone Plume Dispersion & Mating Disruption Engine.

Models insect sex pheromone volatilization and downwind transport across crop canopies:
- Pasquill-Gifford atmospheric stability classification (Classes A-F) from wind & solar flux.
- Briggs rural dispersion coefficients sigma_y(x) and sigma_z(x).
- Gaussian plume equation with ground-boundary reflection for canopy-level concentration (ng/m^3).
- Arrhenius temperature-dependent dispenser emission rate Q(T) from polymeric septa.
- Effective attraction distance, mating disruption radius, and optimal trap/emitter spacing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class PasquillStabilityClass(str, Enum):
    """Pasquill-Gifford atmospheric turbulence stability classes."""
    A_VERY_UNSTABLE = "A"
    B_UNSTABLE = "B"
    C_SLIGHTLY_UNSTABLE = "C"
    D_NEUTRAL = "D"
    E_SLIGHTLY_STABLE = "E"
    F_STABLE = "F"


class TargetPestSpecies(str, Enum):
    """Major lepidopteran & dipteran pests monitored by pheromone lures."""
    SPODOPTERA_LITURA = "spodoptera_litura"      # Tobacco cutworm (Sâu khoang)
    HELICOVERPA_ARMIGERA = "helicoverpa_armigera"  # Cotton bollworm (Sâu đục quả)
    TUTA_ABSOLUTA = "tuta_absoluta"              # Tomato leafminer (Sâu đục lá cà chua)
    PLUTELLA_XYLOSTELLA = "plutella_xylostella"  # Diamondback moth (Sâu tơ)


class PheromoneLureProfile(BaseModel):
    """Species-specific pheromone release and behavioral threshold parameters."""
    species: TargetPestSpecies
    base_release_rate_ug_h_at_25c: float = Field(..., gt=0.0)
    activation_energy_kj_mol: float = Field(42.0, gt=0.0)
    attraction_threshold_ng_m3: float = Field(0.5, gt=0.0, description="Minimum downwind concentration attracting males")
    disruption_threshold_ng_m3: float = Field(5.0, gt=0.0, description="Concentration causing male sensory habituation")


PHEROMONE_CATALOG: dict[TargetPestSpecies, PheromoneLureProfile] = {
    TargetPestSpecies.SPODOPTERA_LITURA: PheromoneLureProfile(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        base_release_rate_ug_h_at_25c=180.0,
        activation_energy_kj_mol=41.5,
        attraction_threshold_ng_m3=0.45,
        disruption_threshold_ng_m3=4.5,
    ),
    TargetPestSpecies.HELICOVERPA_ARMIGERA: PheromoneLureProfile(
        species=TargetPestSpecies.HELICOVERPA_ARMIGERA,
        base_release_rate_ug_h_at_25c=220.0,
        activation_energy_kj_mol=43.0,
        attraction_threshold_ng_m3=0.60,
        disruption_threshold_ng_m3=5.5,
    ),
    TargetPestSpecies.TUTA_ABSOLUTA: PheromoneLureProfile(
        species=TargetPestSpecies.TUTA_ABSOLUTA,
        base_release_rate_ug_h_at_25c=120.0,
        activation_energy_kj_mol=39.8,
        attraction_threshold_ng_m3=0.35,
        disruption_threshold_ng_m3=3.5,
    ),
    TargetPestSpecies.PLUTELLA_XYLOSTELLA: PheromoneLureProfile(
        species=TargetPestSpecies.PLUTELLA_XYLOSTELLA,
        base_release_rate_ug_h_at_25c=95.0,
        activation_energy_kj_mol=38.5,
        attraction_threshold_ng_m3=0.30,
        disruption_threshold_ng_m3=3.0,
    ),
}


class PlumeSimulationResult(BaseModel):
    """Spatial dispersion and effective range metrics for a pheromone dispenser."""
    species: TargetPestSpecies
    stability_class: PasquillStabilityClass
    ambient_temp_c: float
    wind_speed_m_s: float
    emission_rate_ng_s: float
    centerline_conc_at_10m_ng_m3: float
    centerline_conc_at_30m_ng_m3: float
    effective_attraction_range_m: float
    mating_disruption_radius_m: float
    recommended_dispensers_per_ha: int


@dataclass
class PheromoneDispersionEngine:
    """
    Computes atmospheric pheromone dispersion using the Gaussian Plume Model.
    """
    GAS_CONSTANT_R: ClassVar[float] = 8.314  # J / (mol * K)

    # Briggs rural dispersion parameters: sigma_y = a * x * (1 + b*x)^(-0.5)
    # sigma_z = c * x * (1 + d*x)^e
    BRIGGS_RURAL_COEFFS: ClassVar[dict[PasquillStabilityClass, tuple[float, float, float, float, float]]] = {
        PasquillStabilityClass.A_VERY_UNSTABLE: (0.22, 0.0001, 0.20, 0.0, 0.0),
        PasquillStabilityClass.B_UNSTABLE: (0.16, 0.0001, 0.12, 0.0, 0.0),
        PasquillStabilityClass.C_SLIGHTLY_UNSTABLE: (0.11, 0.0001, 0.08, 0.0002, -0.5),
        PasquillStabilityClass.D_NEUTRAL: (0.08, 0.0001, 0.06, 0.0015, -0.5),
        PasquillStabilityClass.E_SLIGHTLY_STABLE: (0.06, 0.0001, 0.03, 0.0003, -1.0),
        PasquillStabilityClass.F_STABLE: (0.04, 0.0001, 0.016, 0.0003, -1.0),
    }

    @staticmethod
    def classify_stability(wind_speed_m_s: float, solar_irradiance_w_m2: float) -> PasquillStabilityClass:
        """Determines Pasquill-Gifford stability class from surface wind and insolation."""
        if solar_irradiance_w_m2 >= 200.0:
            # Daytime
            if wind_speed_m_s < 2.0:
                return (
                    PasquillStabilityClass.A_VERY_UNSTABLE
                    if solar_irradiance_w_m2 >= 600.0
                    else PasquillStabilityClass.B_UNSTABLE
                )
            if wind_speed_m_s < 4.0:
                return (
                    PasquillStabilityClass.B_UNSTABLE
                    if solar_irradiance_w_m2 >= 600.0
                    else PasquillStabilityClass.C_SLIGHTLY_UNSTABLE
                )
            if wind_speed_m_s < 6.0:
                return PasquillStabilityClass.C_SLIGHTLY_UNSTABLE
            return PasquillStabilityClass.D_NEUTRAL
        # Nighttime / dusk (primary moth flight period)
        if wind_speed_m_s < 2.0:
            return PasquillStabilityClass.F_STABLE
        if wind_speed_m_s < 3.5:
            return PasquillStabilityClass.E_SLIGHTLY_STABLE
        return PasquillStabilityClass.D_NEUTRAL

    def compute_sigma_y_z(
        self,
        distance_x_m: float,
        stability: PasquillStabilityClass,
    ) -> tuple[float, float]:
        """Calculates horizontal (sigma_y) and vertical (sigma_z) plume spread in meters."""
        x = max(1.0, distance_x_m)
        a, b, c, d, e = self.BRIGGS_RURAL_COEFFS[stability]
        sigma_y = a * x * ((1.0 + b * x) ** -0.5)
        sigma_z = c * x * ((1.0 + d * x) ** e) if d > 0 else c * x
        return max(0.2, sigma_y), max(0.2, sigma_z)

    def compute_emission_rate_ng_s(
        self,
        profile: PheromoneLureProfile,
        ambient_temp_c: float,
    ) -> float:
        """
        Calculates temperature-adjusted volatilization rate Q(T) in ng/s using Arrhenius law.
        1 ug/h = 1000 / 3600 ng/s = 0.27778 ng/s.
        """
        t_ref_k = 298.15  # 25°C
        t_k = max(273.15, ambient_temp_c + 273.15)
        ea_j = profile.activation_energy_kj_mol * 1000.0
        arrhenius = math.exp((ea_j / self.GAS_CONSTANT_R) * ((1.0 / t_ref_k) - (1.0 / t_k)))
        rate_ug_h = profile.base_release_rate_ug_h_at_25c * arrhenius
        return round(rate_ug_h * (1000.0 / 3600.0), 3)

    def evaluate_concentration_ng_m3(
        self,
        x_m: float,
        y_m: float,
        z_m: float,
        emission_rate_ng_s: float,
        wind_speed_m_s: float,
        stability: PasquillStabilityClass,
        emitter_height_m: float = 1.2,
    ) -> float:
        """
        Gaussian plume equation with total ground reflection:
        C(x, y, z) = [Q / (2 * pi * u * sy * sz)] * exp(-y^2/(2*sy^2)) * [exp(-(z-H)^2/(2*sz^2)) + exp(-(z+H)^2/(2*sz^2))]
        """
        if x_m <= 0.0:
            return 0.0

        u = max(0.5, wind_speed_m_s)
        sy, sz = self.compute_sigma_y_z(x_m, stability)

        prefactor = emission_rate_ng_s / (2.0 * math.pi * u * sy * sz)
        lateral = math.exp(-(y_m**2) / (2.0 * (sy**2)))
        vertical = math.exp(-((z_m - emitter_height_m) ** 2) / (2.0 * (sz**2))) + math.exp(
            -((z_m + emitter_height_m) ** 2) / (2.0 * (sz**2))
        )
        return round(prefactor * lateral * vertical, 4)

    def simulate_plume(
        self,
        species: TargetPestSpecies = TargetPestSpecies.SPODOPTERA_LITURA,
        ambient_temp_c: float = 22.0,
        wind_speed_m_s: float = 1.8,
        solar_irradiance_w_m2: float = 0.0,
        emitter_height_m: float = 1.2,
        canopy_height_m: float = 0.8,
    ) -> PlumeSimulationResult:
        """
        Simulates downwind plume profile and determines attraction and mating disruption ranges.
        """
        profile = PHEROMONE_CATALOG[species]
        stability = self.classify_stability(wind_speed_m_s, solar_irradiance_w_m2)
        q_ng_s = self.compute_emission_rate_ng_s(profile, ambient_temp_c)

        c_10m = self.evaluate_concentration_ng_m3(
            10.0, 0.0, canopy_height_m, q_ng_s, wind_speed_m_s, stability, emitter_height_m
        )
        c_30m = self.evaluate_concentration_ng_m3(
            30.0, 0.0, canopy_height_m, q_ng_s, wind_speed_m_s, stability, emitter_height_m
        )

        # Scan downwind distance (2m to 150m) to find effective ranges
        attraction_range = 0.0
        disruption_radius = 0.0
        for dist in range(2, 152, 2):
            c = self.evaluate_concentration_ng_m3(
                float(dist), 0.0, canopy_height_m, q_ng_s, wind_speed_m_s, stability, emitter_height_m
            )
            if c >= profile.disruption_threshold_ng_m3:
                disruption_radius = float(dist)
            if c >= profile.attraction_threshold_ng_m3:
                attraction_range = float(dist)

        # Estimate mating disruption emitter density per hectare (10,000 m2)
        eff_r = max(5.0, disruption_radius)
        coverage_per_emitter_m2 = math.pi * ((eff_r * 0.65) ** 2)
        dispensers_per_ha = max(4, min(250, math.ceil(10000.0 / coverage_per_emitter_m2)))

        return PlumeSimulationResult(
            species=species,
            stability_class=stability,
            ambient_temp_c=ambient_temp_c,
            wind_speed_m_s=wind_speed_m_s,
            emission_rate_ng_s=q_ng_s,
            centerline_conc_at_10m_ng_m3=c_10m,
            centerline_conc_at_30m_ng_m3=c_30m,
            effective_attraction_range_m=attraction_range,
            mating_disruption_radius_m=disruption_radius,
            recommended_dispensers_per_ha=dispensers_per_ha,
        )
