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


def test_export_json_validity():
    import json
    reporter = FarmIntelligenceReporter(farm_name="JSON Test Farm")
    metrics = [
        AgronomyHealthMetric(
            plot_id="ZONE_A1",
            crop_type="rice",
            ndvi_score=0.72,
            ndwi_score=0.40,
            ndre_score=0.38,
            chlorophyll_level="NORMAL_HEALTHY",
            water_stress_status="OPTIMAL_TURGID",
        )
    ]
    irrigation = [
        IrrigationAuditEntry(
            plot_id="ZONE_A1",
            water_applied_liters=500.0,
            energy_consumed_kwh=1.2,
            cost_vnd=3600.0,
            et0_deficit_compensated=True,
        )
    ]
    report = reporter.build_executive_report(
        health_metrics=metrics,
        irrigation_entries=irrigation,
        resolutions=["Routine irrigation completed."],
    )
    json_str = reporter.export_json(report)
    parsed = json.loads(json_str)

    assert parsed["report_id"] == report.report_id
    assert parsed["total_plots"] == 1
    assert parsed["mean_farm_ndvi"] == 0.72
    assert parsed["total_water_dispatched_liters"] == 500.0
    assert parsed["estimated_daily_operating_cost_vnd"] == 3600.0
    assert len(parsed["plots_under_water_stress"]) == 0


def test_high_water_volume_advisory_bulletin():
    reporter = FarmIntelligenceReporter(farm_name="High Flow Station")
    metrics = [
        AgronomyHealthMetric(
            plot_id="FIELD_1",
            crop_type="maize",
            ndvi_score=0.68,
            ndwi_score=0.20,
            ndre_score=0.35,
            chlorophyll_level="OPTIMAL",
            water_stress_status="OPTIMAL_HYDRATED",
        )
    ]
    # Heavy watering exceeding 10,000 liters
    irrigation = [
        IrrigationAuditEntry(
            plot_id="FIELD_1",
            water_applied_liters=12500.0,
            energy_consumed_kwh=28.5,
            cost_vnd=85500.0,
            et0_deficit_compensated=True,
        )
    ]
    report = reporter.build_executive_report(metrics, irrigation, ["Pump 1-4 active."])
    assert any("Resource Advisory" in b for b in report.advisory_bulletins)
    assert any("10,000 L" in b for b in report.advisory_bulletins)


def test_clean_health_no_anomalies_report():
    reporter = FarmIntelligenceReporter(farm_name="Prime Organic Grid")
    metrics = [
        AgronomyHealthMetric(
            plot_id=f"PLOT_{i}",
            crop_type="coffee",
            ndvi_score=0.80,
            ndwi_score=0.35,
            ndre_score=0.45,
            chlorophyll_level="OPTIMAL",
            water_stress_status="OPTIMAL_HYDRATED",
        )
        for i in range(4)
    ]
    report = reporter.build_executive_report(metrics, [], [])
    assert len(report.plots_under_water_stress) == 0
    assert len(report.plots_with_nutrient_chlorosis) == 0
    assert len(report.advisory_bulletins) == 0

    md = reporter.render_markdown_dossier(report)
    assert "All telemetry parameters within optimal" in md
    assert "No automated override actions dispatched" in md


def test_multi_crop_grid_aggregation():
    reporter = FarmIntelligenceReporter(farm_name="Polyculture Swarm Hub")
    plots = [
        ("P1", "maize", 0.70, 0.20, 0.35, "NORMAL", "OPTIMAL_HYDRATED"),
        ("P2", "rice", 0.80, 0.45, 0.40, "NORMAL", "OPTIMAL_HYDRATED"),
        ("P3", "coffee", 0.60, 0.10, 0.25, "CHLOROSIS_DEFICIENT", "MODERATE_WATER_STRESS"),
        ("P4", "soybean", 0.50, -0.05, 0.20, "NORMAL", "SEVERE_WATER_STRESS"),
    ]
    metrics = [
        AgronomyHealthMetric(
            plot_id=pid, crop_type=c, ndvi_score=nd, ndwi_score=nw, ndre_score=nr,
            chlorophyll_level=chl, water_stress_status=ws
        )
        for pid, c, nd, nw, nr, chl, ws in plots
    ]
    report = reporter.build_executive_report(metrics, [], ["Action required"])

    # Mean NDVI: (0.70 + 0.80 + 0.60 + 0.50) / 4 = 0.65
    assert report.mean_farm_ndvi == 0.65
    assert set(report.plots_under_water_stress) == {"P3", "P4"}
    assert set(report.plots_with_nutrient_chlorosis) == {"P3"}
