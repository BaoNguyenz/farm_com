"""
Integration test suite for Aerial Drone Scouting & UAV Computer Vision RESTful Endpoints.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_api_drone_simulate_flight():
    payload = {
        "mission_id": "TEST-UAV-SORTIE-99",
        "altitude_m": 40.0,
        "initial_battery_pct": 92.0,
        "zone_ids": ["Z_0_0", "Z_0_1"],
    }
    resp = client.post("/api/v1/drone/simulate-flight", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["mission_id"] == "TEST-UAV-SORTIE-99"
    assert data["status"] == "completed"
    assert data["flight_altitude_m"] == 40.0
    assert len(data["zone_surveys"]) == 2
    assert data["flight_duration_minutes"] > 0.0


def test_api_drone_get_latest_survey():
    resp = client.get("/api/v1/drone/surveys/latest")
    assert resp.status_code == 200
    data = resp.json()

    assert "mission_id" in data
    assert "zone_surveys" in data
    assert "battery_consumed_pct" in data


def test_api_drone_anomalies():
    resp = client.get("/api/v1/drone/anomalies")
    assert resp.status_code == 200
    data = resp.json()

    assert "mission_id" in data
    assert "anomalous_zones" in data
    assert isinstance(data["anomalous_zones"], list)
