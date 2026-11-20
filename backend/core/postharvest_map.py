"""
Modified Atmosphere Packaging (MAP) & Cold-Chain Compliance Engine.

Models polymeric film gas permeation dynamics (O2 ingress vs CO2 egress), steady-state
equilibrium modified atmospheres, Botrytis cinerea fungal mold inhibition, and cumulative
cold-chain Degree-Hours compliance tracking for perishable exports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PackagingFilmType(str, Enum):
    """Polymeric packaging film materials."""

    MICRO_PERFORATED_PP = "micro_perforated_pp"  # Laser micro-drilled polypropylene, balanced gas exchange
    LDPE_50_MICRON = "ldpe_50_micron"            # Low-density polyethylene, standard barrier
    HIGH_GAS_PERM_BIO = "high_gas_perm_bio"      # Compostable PLA/PBAT bio-polymer film


@dataclass(frozen=True)
class FilmPermeabilityParams:
    """Film gas transmission properties."""

    o2_permeance_ml_m2_day_atm: float
    co2_permeance_ml_m2_day_atm: float
    water_vapor_transmission_g_m2_day: float

    @property
    def selectivity_ratio_beta(self) -> float:
        """Selectivity ratio beta = P_CO2 / P_O2 (typically 3.0 to 5.0)."""
        return round(self.co2_permeance_ml_m2_day_atm / max(1.0, self.o2_permeance_ml_m2_day_atm), 2)


FILM_CATALOG: dict[PackagingFilmType, FilmPermeabilityParams] = {
    PackagingFilmType.MICRO_PERFORATED_PP: FilmPermeabilityParams(
        o2_permeance_ml_m2_day_atm=2800.0,
        co2_permeance_ml_m2_day_atm=11200.0,
        water_vapor_transmission_g_m2_day=22.0,
    ),
    PackagingFilmType.LDPE_50_MICRON: FilmPermeabilityParams(
        o2_permeance_ml_m2_day_atm=1800.0,
        co2_permeance_ml_m2_day_atm=7200.0,
        water_vapor_transmission_g_m2_day=14.0,
    ),
    PackagingFilmType.HIGH_GAS_PERM_BIO: FilmPermeabilityParams(
        o2_permeance_ml_m2_day_atm=3400.0,
        co2_permeance_ml_m2_day_atm=14500.0,
        water_vapor_transmission_g_m2_day=35.0,
    ),
}


@dataclass
class MAPPackageDesignResult:
    """Steady-state gas composition and pathogen inhibition inside MAP package."""

    film_type: PackagingFilmType
    fruit_mass_kg: float
    package_area_m2: float
    storage_temp_c: float
    equilibrium_o2_pct: float
    equilibrium_co2_pct: float
    botrytis_inhibition_pct: float
    anaerobic_fermentation_risk: bool
    package_status: str


@dataclass
class ColdChainAuditLog:
    """Reefer log tracking thermal excursions during transport."""

    lot_id: str
    total_transit_hours: float
    mean_temp_c: float
    peak_temp_c: float
    cumulative_degree_hours: float
    temp_abuse_hours: float
    cold_chain_breach: bool
    quality_grade: str


class ModifiedAtmospherePackagingEngine:
    """Engine computing MAP gas equilibrium, fungal inhibition, and cold-chain compliance."""

    def __init__(self, film_type: PackagingFilmType = PackagingFilmType.MICRO_PERFORATED_PP) -> None:
        self.film_type = film_type
        self.film_params = FILM_CATALOG[film_type]

    def solve_equilibrium_atmosphere(
        self,
        fruit_mass_kg: float,
        package_area_m2: float,
        storage_temp_c: float = 2.0,
        fruit_r_o2_ml_kg_h: float = 8.5,
    ) -> MAPPackageDesignResult:
        """Solve steady-state O2 and CO2 concentrations inside package.

        At steady state:
        O2 Ingress: (P_O2 * A) * (0.209 - y_O2) = M_fruit * R_O2 * 24h
        CO2 Egress: (P_CO2 * A) * (y_CO2 - 0.0004) = M_fruit * (R_O2 * RQ) * 24h
        """
        # Daily respiration volume in ml
        daily_o2_demand_ml = fruit_mass_kg * fruit_r_o2_ml_kg_h * 24.0
        daily_co2_release_ml = daily_o2_demand_ml * 1.10  # RQ ~ 1.1

        # O2 equilibrium
        p_o2_total = self.film_params.o2_permeance_ml_m2_day_atm * package_area_m2
        delta_o2 = daily_o2_demand_ml / max(1.0, p_o2_total)
        eq_o2_frac = max(0.005, 0.209 - delta_o2)
        eq_o2_pct = round(eq_o2_frac * 100.0, 2)

        # CO2 equilibrium
        p_co2_total = self.film_params.co2_permeance_ml_m2_day_atm * package_area_m2
        delta_co2 = daily_co2_release_ml / max(1.0, p_co2_total)
        eq_co2_frac = min(0.35, 0.0004 + delta_co2)
        eq_co2_pct = round(eq_co2_frac * 100.0, 2)

        # Botrytis cinerea gray mold inhibition:
        # High CO2 (>10%) severely suppresses fungal mycelial growth
        if eq_co2_pct >= 15.0:
            botrytis_inhibition = 92.0
        elif eq_co2_pct >= 10.0:
            botrytis_inhibition = 82.0
        elif eq_co2_pct >= 5.0:
            botrytis_inhibition = 55.0
        else:
            botrytis_inhibition = 20.0

        is_anaerobic = eq_o2_pct < 1.5

        if is_anaerobic:
            status = "CRITICAL_HYPOXIA_OFF_FLAVORS"
        elif 2.0 <= eq_o2_pct <= 5.0 and 10.0 <= eq_co2_pct <= 16.0:
            status = "OPTIMAL_PRESERVATION_WINDOW"
        else:
            status = "SUB_OPTIMAL_ATMOSPHERE"

        return MAPPackageDesignResult(
            film_type=self.film_type,
            fruit_mass_kg=fruit_mass_kg,
            package_area_m2=package_area_m2,
            storage_temp_c=storage_temp_c,
            equilibrium_o2_pct=eq_o2_pct,
            equilibrium_co2_pct=eq_co2_pct,
            botrytis_inhibition_pct=botrytis_inhibition,
            anaerobic_fermentation_risk=is_anaerobic,
            package_status=status,
        )

    def audit_cold_chain_transit(
        self,
        lot_id: str,
        hourly_temperatures_c: list[float],
        base_temp_c: float = 3.0,
        max_allowable_degree_hours: float = 45.0,
    ) -> ColdChainAuditLog:
        """Audit shipment reefer data logger for temperature excursions."""
        total_hours = float(len(hourly_temperatures_c))
        if total_hours == 0:
            return ColdChainAuditLog(
                lot_id=lot_id,
                total_transit_hours=0.0,
                mean_temp_c=base_temp_c,
                peak_temp_c=base_temp_c,
                cumulative_degree_hours=0.0,
                temp_abuse_hours=0.0,
                cold_chain_breach=False,
                quality_grade="GRADE_AAA",
            )

        mean_temp = round(sum(hourly_temperatures_c) / total_hours, 2)
        peak_temp = max(hourly_temperatures_c)

        degree_hours = 0.0
        abuse_hours = 0.0

        for t in hourly_temperatures_c:
            if t > base_temp_c:
                degree_hours += (t - base_temp_c) * 1.0
            if t > 8.0:
                abuse_hours += 1.0

        degree_hours = round(degree_hours, 1)
        breached = degree_hours > max_allowable_degree_hours or peak_temp > 15.0

        if degree_hours <= 15.0 and peak_temp <= 5.0:
            grade = "GRADE_AAA_PREMIUM"
        elif not breached:
            grade = "GRADE_AA_STANDARD"
        else:
            grade = "GRADE_B_DOMESTIC_DOWNGRADE"

        return ColdChainAuditLog(
            lot_id=lot_id,
            total_transit_hours=total_hours,
            mean_temp_c=mean_temp,
            peak_temp_c=peak_temp,
            cumulative_degree_hours=degree_hours,
            temp_abuse_hours=abuse_hours,
            cold_chain_breach=breached,
            quality_grade=grade,
        )
