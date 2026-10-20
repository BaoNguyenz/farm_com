"""
Unit tests for Multi-Agent Farm Intelligence & Analytics Reporter
"""
import pytest
from backend.agents.analytics_reporter import (
    FarmIntelligenceReporter,
    AgronomyHealthMetric,
    IrrigationAuditEntry,
)


def test_executive_report_builder():
    reporter = FarmIntelligenceReporter(farm_name="Da Lat Test Matrix")

    metrics = [
        AgronomyHealthMetric(
            plot_id="PLOT_0_0",
            crop_type="maize",
            ndvi_score=0.75,
            ndwi_score=0.35,
            ndre_score=0.42,
            chlorophyll_level="OPTIMAL",
            water_stress_status="NO_STRESS",
        ),
        AgronomyHealthMetric(
            plot_id="PLOT_0_1",
            crop_type="maize",
            ndvi_score=0.45,
            ndwi_score=-0.05,
            ndre_score=0.25,
            chlorophyll_level="CHLOROSIS_DEFICIENT",
            water_stress_status="MODERATE_WATER_STRESS",
        ),
    ]

    irrigation = [
        IrrigationAuditEntry(
            plot_id="PLOT_0_1",
            water_applied_liters=1200.0,
            energy_consumed_kwh=3.5,
            cost_vnd=10500.0,
            et0_deficit_compensated=True,
        )
    ]

    report = reporter.build_executive_report(
        health_metrics=metrics,
        irrigation_entries=irrigation,
        resolutions=["Dispatched 1200L irrigation to PLOT_0_1"],
    )

    assert report.total_plots == 2
    assert report.mean_farm_ndvi == 0.60
    assert "PLOT_0_1" in report.plots_under_water_stress
    assert "PLOT_0_1" in report.plots_with_nutrient_chlorosis

    md = reporter.render_markdown_dossier(report)
    assert "# 🌾 Da Lat Test Matrix" in md
    assert "PLOT_0_1" in md
