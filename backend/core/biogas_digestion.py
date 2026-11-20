"""
Anaerobic Digestion (AD) & Biogas Kinetic Engine.

Simulates anaerobic degradation of agricultural biomass, crop residues, and aquaponic sludge.
Implements Hill/ADM1 kinetic approximations for volatile solids (VS) conversion, methane yield,
and VFA/TIC digester acidification monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeedstockType(str, Enum):
    """Agricultural organic waste substrates."""

    CROP_RESIDUES = "crop_residues"       # Pruned strawberry/tomato vines, high C:N
    AQUAPONIC_SLUDGE = "aquaponic_sludge" # Fish feces and biofilter backwash, high N
    DAIRY_MANURE = "dairy_manure"         # Bovine manure, high buffering capacity
    CO_DIGESTION_MIX = "co_digestion_mix" # 60% crop residues + 40% manure/sludge optimal blend


@dataclass(frozen=True)
class FeedstockCharacteristics:
    """Biochemical methane potential (BMP) parameters of substrate."""

    total_solids_pct: float       # TS % (fresh weight basis)
    volatile_solids_pct_ts: float # VS % of TS
    bmp_m3_ch4_per_kg_vs: float   # Specific methane yield
    methane_fraction_pct: float   # % CH4 in raw biogas
    nitrogen_content_g_kg: float  # Total Kjeldahl Nitrogen
    c_to_n_ratio: float           # Carbon to nitrogen ratio


FEEDSTOCK_CATALOG: dict[FeedstockType, FeedstockCharacteristics] = {
    FeedstockType.CROP_RESIDUES: FeedstockCharacteristics(
        total_solids_pct=18.5,
        volatile_solids_pct_ts=82.0,
        bmp_m3_ch4_per_kg_vs=0.32,
        methane_fraction_pct=56.0,
        nitrogen_content_g_kg=14.0,
        c_to_n_ratio=32.0,
    ),
    FeedstockType.AQUAPONIC_SLUDGE: FeedstockCharacteristics(
        total_solids_pct=7.5,
        volatile_solids_pct_ts=74.0,
        bmp_m3_ch4_per_kg_vs=0.28,
        methane_fraction_pct=64.0,
        nitrogen_content_g_kg=38.0,
        c_to_n_ratio=9.5,
    ),
    FeedstockType.DAIRY_MANURE: FeedstockCharacteristics(
        total_solids_pct=12.0,
        volatile_solids_pct_ts=78.0,
        bmp_m3_ch4_per_kg_vs=0.24,
        methane_fraction_pct=60.0,
        nitrogen_content_g_kg=22.0,
        c_to_n_ratio=18.5,
    ),
    FeedstockType.CO_DIGESTION_MIX: FeedstockCharacteristics(
        total_solids_pct=14.5,
        volatile_solids_pct_ts=80.0,
        bmp_m3_ch4_per_kg_vs=0.35,
        methane_fraction_pct=62.5,
        nitrogen_content_g_kg=24.0,
        c_to_n_ratio=24.5,
    ),
}


@dataclass
class DigestionSimulationResult:
    """Daily output and health state of the anaerobic digester."""

    feedstock: FeedstockType
    feed_mass_kg_day: float
    digester_temp_c: float
    hydraulic_retention_time_days: float
    volatile_solids_fed_kg: float
    vs_destruction_efficiency_pct: float
    daily_biogas_m3: float
    daily_methane_m3: float
    daily_co2_m3: float
    methane_content_pct: float
    vfa_mg_l: float
    tic_alkalinity_mg_l: float
    vfa_tic_ratio: float
    health_status: str
    acidification_hazard: bool
    digestate_effluent_m3: float


class AnaerobicDigesterEngine:
    """Simulates mesophilic / psychrophilic anaerobic digestion kinetics."""

    def __init__(
        self,
        digester_volume_m3: float = 25.0,
        operating_temp_c: float = 37.0,
    ) -> None:
        self.digester_volume_m3 = digester_volume_m3
        self.operating_temp_c = operating_temp_c

    def _calculate_temperature_coefficient(self, temp_c: float) -> float:
        """Arrhenius-style temperature factor for methanogenesis (optimal 37C)."""
        if temp_c >= 37.0:
            return 1.0
        if temp_c < 15.0:
            return 0.20
        # Linear/exponential interpolation between 15C and 37C
        return round(0.20 + 0.80 * ((temp_c - 15.0) / 22.0), 3)

    def simulate_digestion(
        self,
        feedstock_type: FeedstockType,
        feed_mass_kg_day: float,
        override_temp_c: float | None = None,
        retention_days: float = 25.0,
    ) -> DigestionSimulationResult:
        """Simulate continuous daily digestion cycle."""
        temp = override_temp_c if override_temp_c is not None else self.operating_temp_c
        props = FEEDSTOCK_CATALOG[feedstock_type]
        temp_factor = self._calculate_temperature_coefficient(temp)

        # Volatile Solids calculation
        total_solids_kg = feed_mass_kg_day * (props.total_solids_pct / 100.0)
        volatile_solids_kg = total_solids_kg * (props.volatile_solids_pct_ts / 100.0)

        # Destruction efficiency based on retention time and temp:
        # Base 65% VS destruction under 25-day HRT at 37C
        hrt_factor = min(1.15, max(0.40, retention_days / 25.0))
        vs_destruction_pct = round(min(80.0, 62.0 * temp_factor * hrt_factor), 1)

        vs_destroyed_kg = volatile_solids_kg * (vs_destruction_pct / 100.0)

        # Methane & Biogas production
        ch4_m3 = round(vs_destroyed_kg * props.bmp_m3_ch4_per_kg_vs, 2)
        methane_pct = props.methane_fraction_pct
        biogas_m3 = round(ch4_m3 / (methane_pct / 100.0), 2)
        co2_m3 = round(biogas_m3 - ch4_m3, 2)

        # Digester health: VFA / TIC ratio calculation
        # Overloading: when Organic Loading Rate (OLR = VS / V_digester) > 3.5 kg VS/m3*day
        olr = volatile_solids_kg / max(1.0, self.digester_volume_m3)
        base_vfa = 800.0  # mg/L acetic acid equivalent
        base_tic = 3800.0  # mg/L CaCO3 equivalent

        vfa_elevated = base_vfa + max(0.0, (olr - 2.5) * 1200.0) + (1.0 - temp_factor) * 900.0
        vfa_mg_l = round(vfa_elevated, 1)
        tic_mg_l = round(base_tic + (feed_mass_kg_day * 0.4), 1)
        vfa_tic = round(vfa_mg_l / max(1.0, tic_mg_l), 2)

        if vfa_tic < 0.30:
            health_status = "stable_optimal"
            hazard = False
        elif vfa_tic <= 0.40:
            health_status = "caution_elevated_vfa"
            hazard = False
        else:
            health_status = "sour_acidification_alarm"
            hazard = True

        # Liquid digestate volume: approximately equal to water in feed
        effluent_m3 = round((feed_mass_kg_day * (1.0 - props.total_solids_pct / 100.0)) / 1000.0, 3)

        return DigestionSimulationResult(
            feedstock=feedstock_type,
            feed_mass_kg_day=feed_mass_kg_day,
            digester_temp_c=temp,
            hydraulic_retention_time_days=retention_days,
            volatile_solids_fed_kg=round(volatile_solids_kg, 2),
            vs_destruction_efficiency_pct=vs_destruction_pct,
            daily_biogas_m3=biogas_m3,
            daily_methane_m3=ch4_m3,
            daily_co2_m3=co2_m3,
            methane_content_pct=methane_pct,
            vfa_mg_l=vfa_mg_l,
            tic_alkalinity_mg_l=tic_mg_l,
            vfa_tic_ratio=vfa_tic,
            health_status=health_status,
            acidification_hazard=hazard,
            digestate_effluent_m3=effluent_m3,
        )
