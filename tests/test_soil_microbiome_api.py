"""
Integration test suite for Soil Microbiome RESTful API endpoints.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_farm_soil_health() -> None:
    res = client.get("/api/v1/soil-microbiome/health")
    assert res.status_code == 200
    data = res.json()
    assert "average_soil_health_index" in data
    assert "total_estimated_leached_n_kg" in data
    assert "zone_audits" in data
    assert len(data["zone_audits"]) > 0


def test_get_zone_soil_audit_success() -> None:
    res = client.get("/api/v1/soil-microbiome/zone/Z_0_0")
    assert res.status_code == 200
    data = res.json()
    assert data["zone_id"] == "Z_0_0"
    assert "soil_health_index" in data
    assert "root_hypoxia_index" in data
    assert "leaching_risk_tier" in data


def test_get_zone_soil_audit_not_found() -> None:
    res = client.get("/api/v1/soil-microbiome/zone/NONEXISTENT_ZONE")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_get_leaching_risk_overview() -> None:
    res = client.get("/api/v1/soil-microbiome/leaching-risk")
    assert res.status_code == 200
    data = res.json()
    assert "total_at_risk_zones" in data
    assert "mitigation_protocol" in data
    assert "at_risk_details" in data


def test_reinoculate_zone_success() -> None:
    payload = {
        "zone_id": "Z_0_0",
        "organic_amendment_kg": 60.0,
        "bio_inoculant": True,
    }
    res = client.post("/api/v1/soil-microbiome/reinoculate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["zone_id"] == "Z_0_0"
    assert "post_treatment_profile" in data
    assert data["post_treatment_profile"]["beneficial_bacteria_cfu_per_g"] > 0


def test_reinoculate_zone_not_found() -> None:
    payload = {
        "zone_id": "UNKNOWN_99",
        "organic_amendment_kg": 50.0,
        "bio_inoculant": True,
    }
    res = client.post("/api/v1/soil-microbiome/reinoculate", json=payload)
    assert res.status_code == 404
