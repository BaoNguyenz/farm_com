"""
Integration test suite for Post-Harvest Cold-Chain RESTful API endpoints.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_all_chambers() -> None:
    res = client.get("/api/v1/cold-chain/chambers")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    chamber_ids = [c["chamber_id"] for c in data]
    assert "CHAMBER-A1" in chamber_ids


def test_audit_cold_chain_shelf_life() -> None:
    res = client.get("/api/v1/cold-chain/audit")
    assert res.status_code == 200
    data = res.json()
    assert "chambers" in data
    assert isinstance(data["chambers"], list)
    assert len(data["chambers"]) >= 2
    for proj in data["chambers"]:
        assert "remaining_shelf_life_days" in proj
        assert "freshness_index_pct" in proj
        assert "quality_grade" in proj


def test_get_chamber_details_success() -> None:
    res = client.get("/api/v1/cold-chain/chamber/CHAMBER-A1")
    assert res.status_code == 200
    data = res.json()
    assert "chamber" in data
    assert "shelf_life_projection" in data
    assert data["chamber"]["chamber_id"] == "CHAMBER-A1"


def test_get_chamber_details_not_found() -> None:
    res = client.get("/api/v1/cold-chain/chamber/CHAMBER-NONEXISTENT")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_adjust_chamber_temperature_success() -> None:
    payload = {
        "chamber_id": "CHAMBER-A1",
        "target_temp_c": 1.5,
    }
    res = client.post("/api/v1/cold-chain/adjust-temperature", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["new_target_temp_c"] == 1.5
    assert "updated_shelf_life_days" in data


def test_adjust_chamber_temperature_not_found() -> None:
    payload = {
        "chamber_id": "CHAMBER-UNKNOWN",
        "target_temp_c": 4.0,
    }
    res = client.post("/api/v1/cold-chain/adjust-temperature", json=payload)
    assert res.status_code == 404


def test_purge_chamber_ethylene_success() -> None:
    payload = {"chamber_id": "CHAMBER-B2"}
    res = client.post("/api/v1/cold-chain/purge-ethylene", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["ethylene_ppm"] == 0.02
    assert data["scrubber_active"] is True


def test_purge_chamber_ethylene_not_found() -> None:
    payload = {"chamber_id": "CHAMBER-UNKNOWN"}
    res = client.post("/api/v1/cold-chain/purge-ethylene", json=payload)
    assert res.status_code == 404
