"""
Integration test suite for Autonomous Rover Fleet Swarm RESTful API endpoints.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_fleet_telemetry() -> None:
    res = client.get("/api/v1/rovers/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["total_rovers"] >= 4
    assert "average_battery_soc" in data
    assert "rovers" in data
    assert len(data["rovers"]) >= 4


def test_get_single_rover_telemetry_success() -> None:
    res = client.get("/api/v1/rovers/ROVER-ALPHA")
    assert res.status_code == 200
    data = res.json()
    assert data["rover_id"] == "ROVER-ALPHA"
    assert "battery_soc" in data
    assert "wheel_slip_pct" in data


def test_get_single_rover_telemetry_not_found() -> None:
    res = client.get("/api/v1/rovers/ROVER-NONEXISTENT")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_dispatch_rover_mission() -> None:
    payload = {
        "plot_id": "Z_0_0",
        "row_index": 2,
        "priority": "urgent_infestation",
    }
    res = client.post("/api/v1/rovers/dispatch", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["target_plot_id"] == "Z_0_0"
    assert data["target_row_index"] == 2
    assert data["assigned_rover_id"] is not None


def test_simulate_fleet_cycle() -> None:
    payload = {
        "duration_seconds": 60.0,
        "soil_moisture_pct": 52.0,
    }
    res = client.post("/api/v1/rovers/cycle", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "active_patrolling_count" in data
    assert "total_weeds_eradicated" in data


def test_recall_fleet_to_dock() -> None:
    res = client.post("/api/v1/rovers/recall")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["recalled_count"] >= 4
    for r in data["fleet"]:
        assert r["task"] == "RETURNING_TO_DOCK"
