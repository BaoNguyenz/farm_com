"""
Smart Optical-Pheromone Pest Trapping & Pest Degree-Day (PDD) Phenology Engine.

Models automated Edge-AI sticky trap vision telemetry and insect population dynamics:
- Pest Degree-Day (PDD) thermal accumulation for egg, larva, pupa, and adult flight emergence.
- Optical camera sticky-trap catch aggregation with confidence-weighted filtering.
- Economic Threshold (ET) and Economic Injury Level (EIL) decision triggers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from backend.core.pheromone_dispersion import TargetPestSpecies


class PestLifecycleStage(str, Enum):
    """Developmental stage derived from cumulative Pest Degree-Days (PDD)."""
    EGG = "egg"
    LARVA_FEEDING = "larva_feeding"
    PUPA = "pupa"
    ADULT_FLIGHT_PEAK = "adult_flight_peak"


class TrapAlertLevel(str, Enum):
    """Actionable pest threshold alert status."""
    LOW_MONITORING = "low_monitoring"
    ECONOMIC_THRESHOLD_EXCEEDED = "economic_threshold_exceeded"
    CRITICAL_OUTBREAK_EIL = "critical_outbreak_eil"


class PestPhenologyParams(BaseModel):
    """Species-specific thermal thresholds and Economic Injury Levels."""
    species: TargetPestSpecies
    t_base_c: float = Field(..., description="Lower developmental threshold (°C)")
    t_upper_c: float = Field(34.0, description="Upper developmental cutoff (°C)")
    pdd_egg_to_larva: float = Field(60.0)
    pdd_larva_to_pupa: float = Field(220.0)
    pdd_pupa_to_adult: float = Field(360.0)
    economic_threshold_moths_per_trap: float = Field(5.0, gt=0.0)
    economic_injury_level_moths_per_trap: float = Field(12.0, gt=0.0)


PEST_PHENOLOGY_CATALOG: dict[TargetPestSpecies, PestPhenologyParams] = {
    TargetPestSpecies.SPODOPTERA_LITURA: PestPhenologyParams(
        species=TargetPestSpecies.SPODOPTERA_LITURA,
        t_base_c=10.5,
        t_upper_c=35.0,
        pdd_egg_to_larva=55.0,
        pdd_larva_to_pupa=210.0,
        pdd_pupa_to_adult=350.0,
        economic_threshold_moths_per_trap=5.0,
        economic_injury_level_moths_per_trap=12.0,
    ),
    TargetPestSpecies.HELICOVERPA_ARMIGERA: PestPhenologyParams(
        species=TargetPestSpecies.HELICOVERPA_ARMIGERA,
        t_base_c=11.0,
        t_upper_c=36.0,
        pdd_egg_to_larva=50.0,
        pdd_larva_to_pupa=230.0,
        pdd_pupa_to_adult=380.0,
        economic_threshold_moths_per_trap=4.0,
        economic_injury_level_moths_per_trap=10.0,
    ),
    TargetPestSpecies.TUTA_ABSOLUTA: PestPhenologyParams(
        species=TargetPestSpecies.TUTA_ABSOLUTA,
        t_base_c=8.0,
        t_upper_c=33.0,
        pdd_egg_to_larva=45.0,
        pdd_larva_to_pupa=175.0,
        pdd_pupa_to_adult=290.0,
        economic_threshold_moths_per_trap=3.0,
        economic_injury_level_moths_per_trap=8.0,
    ),
    TargetPestSpecies.PLUTELLA_XYLOSTELLA: PestPhenologyParams(
        species=TargetPestSpecies.PLUTELLA_XYLOSTELLA,
        t_base_c=7.5,
        t_upper_c=32.0,
        pdd_egg_to_larva=40.0,
        pdd_larva_to_pupa=150.0,
        pdd_pupa_to_adult=250.0,
        economic_threshold_moths_per_trap=6.0,
        economic_injury_level_moths_per_trap=15.0,
    ),
}


class OpticalTrapCatch(BaseModel):
    """Daily Edge-AI optical sticky-trap detection report."""
    trap_id: str
    species: TargetPestSpecies
    raw_count: int = Field(..., ge=0)
    edge_ai_confidence: float = Field(0.92, ge=0.0, le=1.0)
    nights_active: int = Field(1, ge=1)


class TrapPopulationAudit(BaseModel):
    """Aggregated pest pressure, phenology stage, and intervention recommendation."""
    species: TargetPestSpecies
    cumulative_pdd: float
    lifecycle_stage: PestLifecycleStage
    mean_moths_per_trap_night: float
    economic_threshold: float
    economic_injury_level: float
    alert_level: TrapAlertLevel
    recommended_intervention: str


@dataclass
class SmartPestTrapEngine:
    """
    Evaluates Pest Degree-Day phenology and optical pheromone trap catches.
    """

    @staticmethod
    def compute_daily_pdd(
        t_min_c: float,
        t_max_c: float,
        params: PestPhenologyParams,
    ) -> float:
        """Calculates daily Pest Degree-Days using horizontal cutoff averaging."""
        t_avg = (t_min_c + t_max_c) / 2.0
        t_clamped = min(t_avg, params.t_upper_c)
        return round(max(0.0, t_clamped - params.t_base_c), 2)

    @staticmethod
    def classify_lifecycle_stage(
        cumulative_pdd: float,
        params: PestPhenologyParams,
    ) -> PestLifecycleStage:
        """Determines insect developmental stage from accumulated degree-days."""
        if cumulative_pdd < params.pdd_egg_to_larva:
            return PestLifecycleStage.EGG
        if cumulative_pdd < params.pdd_larva_to_pupa:
            return PestLifecycleStage.LARVA_FEEDING
        if cumulative_pdd < params.pdd_pupa_to_adult:
            return PestLifecycleStage.PUPA
        return PestLifecycleStage.ADULT_FLIGHT_PEAK

    def evaluate_trap_network(
        self,
        species: TargetPestSpecies,
        catches: list[OpticalTrapCatch],
        cumulative_pdd: float = 365.0,
    ) -> TrapPopulationAudit:
        """
        Aggregates optical trap counts (filtered by Edge AI confidence >= 0.70)
        and determines Economic Threshold / Economic Injury Level compliance.
        """
        params = PEST_PHENOLOGY_CATALOG[species]
        stage = self.classify_lifecycle_stage(cumulative_pdd, params)

        if not catches:
            mean_catch = 0.0
        else:
            weighted_counts = [
                (c.raw_count * (1.0 if c.edge_ai_confidence >= 0.70 else 0.5)) / c.nights_active
                for c in catches
            ]
            mean_catch = round(sum(weighted_counts) / len(weighted_counts), 2)

        if mean_catch >= params.economic_injury_level_moths_per_trap:
            alert = TrapAlertLevel.CRITICAL_OUTBREAK_EIL
            action = "EMERGENCY_BIOCONTROL_SATURATION_AND_MATING_DISRUPTION"
        elif mean_catch >= params.economic_threshold_moths_per_trap:
            alert = TrapAlertLevel.ECONOMIC_THRESHOLD_EXCEEDED
            action = "DEPLOY_PHEROMONE_DISRUPTION_AND_TRICHOGRAMMA_EGG_PARASITOIDS"
        else:
            alert = TrapAlertLevel.LOW_MONITORING
            action = "CONTINUE_OPTICAL_MONITORING_NO_SPRAY_REQUIRED"

        return TrapPopulationAudit(
            species=species,
            cumulative_pdd=round(cumulative_pdd, 1),
            lifecycle_stage=stage,
            mean_moths_per_trap_night=mean_catch,
            economic_threshold=params.economic_threshold_moths_per_trap,
            economic_injury_level=params.economic_injury_level_moths_per_trap,
            alert_level=alert,
            recommended_intervention=action,
        )
