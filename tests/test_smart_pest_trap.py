"""
Unit test suite for Smart Optical-Pheromone Pest Trapping & Pest Degree-Day Engine.
"""

from backend.core.pheromone_dispersion import TargetPestSpecies
from backend.core.smart_pest_trap import (
    PEST_PHENOLOGY_CATALOG,
    OpticalTrapCatch,
    PestLifecycleStage,
    SmartPestTrapEngine,
    TrapAlertLevel,
)


def test_daily_pdd_accumulation():
    """Verify daily Pest Degree-Days calculation with lower base and upper cutoff."""
    engine = SmartPestTrapEngine()
    params = PEST_PHENOLOGY_CATALOG[TargetPestSpecies.SPODOPTERA_LITURA]  # T_base=10.5, T_upper=35

    # Cold day below base temperature -> 0 PDD
    assert engine.compute_daily_pdd(6.0, 12.0, params) == 0.0
    # Moderate day (avg 20.5°C) -> 10.0 PDD
    assert engine.compute_daily_pdd(15.0, 26.0, params) == 10.0
    # Extreme hot day capped at 35°C -> 24.5 PDD
    assert engine.compute_daily_pdd(32.0, 42.0, params) == 24.5


def test_lifecycle_stage_transitions():
    """Verify PDD thresholds map to egg, larva, pupa, and adult flight peak."""
    engine = SmartPestTrapEngine()
    params = PEST_PHENOLOGY_CATALOG[TargetPestSpecies.TUTA_ABSOLUTA]

    assert engine.classify_lifecycle_stage(20.0, params) == PestLifecycleStage.EGG
    assert engine.classify_lifecycle_stage(100.0, params) == PestLifecycleStage.LARVA_FEEDING
    assert engine.classify_lifecycle_stage(220.0, params) == PestLifecycleStage.PUPA
    assert engine.classify_lifecycle_stage(310.0, params) == PestLifecycleStage.ADULT_FLIGHT_PEAK


def test_trap_network_low_monitoring():
    """Verify low trap catches stay in LOW_MONITORING without spray."""
    engine = SmartPestTrapEngine()
    catches = [
        OpticalTrapCatch(trap_id="TRAP-01", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=2),
        OpticalTrapCatch(trap_id="TRAP-02", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=1),
    ]

    audit = engine.evaluate_trap_network(TargetPestSpecies.SPODOPTERA_LITURA, catches, cumulative_pdd=360.0)
    assert audit.mean_moths_per_trap_night == 1.5
    assert audit.alert_level == TrapAlertLevel.LOW_MONITORING
    assert "NO_SPRAY" in audit.recommended_intervention


def test_trap_network_economic_threshold_exceeded():
    """Verify catches exceeding ET (5.0) trigger pheromone disruption and Trichogramma."""
    engine = SmartPestTrapEngine()
    catches = [
        OpticalTrapCatch(trap_id="TRAP-01", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=7),
        OpticalTrapCatch(trap_id="TRAP-02", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=6),
    ]

    audit = engine.evaluate_trap_network(TargetPestSpecies.SPODOPTERA_LITURA, catches, cumulative_pdd=365.0)
    assert audit.mean_moths_per_trap_night == 6.5
    assert audit.alert_level == TrapAlertLevel.ECONOMIC_THRESHOLD_EXCEEDED
    assert "TRICHOGRAMMA" in audit.recommended_intervention


def test_trap_network_critical_eil_outbreak():
    """Verify catches exceeding EIL (12.0) trigger critical outbreak intervention."""
    engine = SmartPestTrapEngine()
    catches = [
        OpticalTrapCatch(trap_id="TRAP-01", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=15),
        OpticalTrapCatch(trap_id="TRAP-02", species=TargetPestSpecies.SPODOPTERA_LITURA, raw_count=14),
    ]

    audit = engine.evaluate_trap_network(TargetPestSpecies.SPODOPTERA_LITURA, catches, cumulative_pdd=370.0)
    assert audit.alert_level == TrapAlertLevel.CRITICAL_OUTBREAK_EIL
    assert "EMERGENCY" in audit.recommended_intervention


def test_empty_trap_catches_safe():
    """Verify empty trap list returns 0 catch and LOW_MONITORING."""
    engine = SmartPestTrapEngine()
    audit = engine.evaluate_trap_network(TargetPestSpecies.PLUTELLA_XYLOSTELLA, [], cumulative_pdd=100.0)
    assert audit.mean_moths_per_trap_night == 0.0
    assert audit.alert_level == TrapAlertLevel.LOW_MONITORING
