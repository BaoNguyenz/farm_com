"""
Multi-Agent Farm Intelligence and Executive Analytics Reporter.
Synthesizes telemetry, spectral vegetative index observations,
agronomy health diagnoses, and market intelligence into comprehensive audits.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class AgronomyHealthMetric:
    """Individual plot agronomy index metric."""
    plot_id: str
    crop_type: str
    ndvi_score: float
    ndwi_score: float
    ndre_score: float
    chlorophyll_level: str
    water_stress_status: str


@dataclass
class IrrigationAuditEntry:
    """Water application telemetry and efficiency record."""
    plot_id: str
    water_applied_liters: float
    energy_consumed_kwh: float
    cost_vnd: float
    et0_deficit_compensated: bool


@dataclass
class FarmDailyExecutiveReport:
    """Comprehensive daily agricultural intelligence dossier."""
    report_id: str
    generated_at: str
    total_plots: int
    mean_farm_ndvi: float
    total_water_dispatched_liters: float
    total_energy_kwh: float
    estimated_daily_operating_cost_vnd: float
    plots_under_water_stress: List[str]
    plots_with_nutrient_chlorosis: List[str]
    commander_resolutions: List[str]
    advisory_bulletins: List[str] = field(default_factory=list)


class FarmIntelligenceReporter:
    """Compiles multi-agent consensus audits into human-readable dossiers."""

    def __init__(self, farm_name: str = "Farm_com Autonomous Ag Swarm"):
        self.farm_name = farm_name

    def build_executive_report(
        self,
        health_metrics: List[AgronomyHealthMetric],
        irrigation_entries: List[IrrigationAuditEntry],
        resolutions: List[str],
    ) -> FarmDailyExecutiveReport:
        """Assembles telemetry records into a structured executive report."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_id = f"REP-{datetime.now().strftime('%Y%m%d%H%M')}"

        stressed_plots = []
        chlorosis_plots = []
        total_ndvi = 0.0

        for m in health_metrics:
            total_ndvi += m.ndvi_score
            if "STRESS" in m.water_stress_status.upper():
                stressed_plots.append(m.plot_id)
            if "CHLOROSIS" in m.chlorophyll_level.upper() or "DEFICIENT" in m.chlorophyll_level.upper():
                chlorosis_plots.append(m.plot_id)

        mean_ndvi = round(total_ndvi / max(1, len(health_metrics)), 3)
