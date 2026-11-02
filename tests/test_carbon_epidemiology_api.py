"""
Integration tests for Carbon Accounting and Fungal Epidemiology REST APIs.
Tests farm footprint audits, zone-level carbon calculations,
biosecurity risk profiling, and IPM advisory retrieval.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_carbon_footprint_api(client):
    res = client.get("/api/v1/carbon/footprint?elapsed_days=3.0&water_liters=6000.0&nitrogen_kg=3.0")
    assert res.status_code == 200
    data = res.json()
    assert "farm_id" in data
    assert data["elapsed_days"] == 3.0
    assert data["total_electricity_kwh"] > 0.0
    assert data["scope1_emissions_kg_co2e"] > 0.0
    assert data["scope2_emissions_kg_co2e"] > 0.0
    assert "carbon_rating" in data
    assert len(data["zone_breakdowns"]) > 0


def test_carbon_zone_footprint_api(client):
    res = client.get("/api/v1/carbon/zones/Z_0_0?water_liters=200.0&nitrogen_kg=0.2")
    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == "Z_0_0"
    assert "electricity_emissions_kg_co2e" in data
    assert "fertilizer_emissions_kg_co2e" in data
    assert "carbon_sequestration_kg_co2e" in data

    # 404 test
    res_404 = client.get("/api/v1/carbon/zones/Z_99_99")
    assert res_404.status_code == 404


def test_carbon_factors_api(client):
    res = client.get("/api/v1/carbon/factors")
    assert res.status_code == 200
    data = res.json()
    assert data["grid_electricity_kg_co2e_per_kwh"] == 0.7221
    assert data["pumping_energy_kwh_per_m3"] == 0.35


def test_epidemiology_biosecurity_api(client):
    res = client.get("/api/v1/epidemiology/biosecurity")
    assert res.status_code == 200
    data = res.json()
    assert "farm_id" in data
    assert data["total_zones_monitored"] > 0
    assert "average_pathogen_risk_score" in data
    assert "highest_threat" in data


def test_epidemiology_zone_profile_api(client):
    res = client.get("/api/v1/epidemiology/zones/Z_0_0")
    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == "Z_0_0"
    assert len(data["pathogen_risks"]) == 3
    assert "max_risk_score" in data
    assert "primary_threat" in data
    assert "recommended_action" in data

    res_404 = client.get("/api/v1/epidemiology/zones/Z_99_99")
    assert res_404.status_code == 404


def test_epidemiology_ipm_advisories_api(client):
    res = client.get("/api/v1/epidemiology/ipm-advisories")
    assert res.status_code == 200
    advisories = res.json()
    assert isinstance(advisories, list)
