"""
Integration tests for Scenario Benchmarks RESTful API Endpoints (Task 7.1 - 7.3)
Tests scenario catalog retrieval, single and batch execution, and scorecard reporting.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_list_scenarios(client):
    res = client.get("/api/v1/scenarios/list")
    assert res.status_code == 200
    catalog = res.json()
    assert len(catalog) >= 4
    scenario_ids = [s["id"] for s in catalog]
    assert "scenario_drought_shock" in scenario_ids
    assert "scenario_fungal_outbreak" in scenario_ids


def test_api_run_single_scenario(client):
    res = client.post("/api/v1/scenarios/run", json={
        "scenario_id": "drought_shock",
        "broadcast_updates": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["type"] == "single_scenario_completed"
    assert "result" in data
    assert data["result"]["scenario_id"] == "scenario_drought_shock"
    assert data["result"]["score"] >= 70.0


def test_api_run_all_scenarios_and_latest(client):
    res = client.post("/api/v1/scenarios/run", json={
        "scenario_id": "all",
        "broadcast_updates": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["type"] == "suite_completed"
    assert "report" in data
    report = data["report"]
    assert report["total_scenarios"] == 4
    assert report["composite_grade"] in ("A+", "A", "B")

    # Query latest endpoint
    res_latest = client.get("/api/v1/scenarios/latest")
    assert res_latest.status_code == 200
    latest_data = res_latest.json()
    assert latest_data["status"] == "success"
    assert latest_data["report"] is not None
    assert latest_data["report"]["composite_score"] == report["composite_score"]


def test_api_run_invalid_scenario_404(client):
    res = client.post("/api/v1/scenarios/run", json={
        "scenario_id": "non_existent_typhoon",
        "broadcast_updates": False
    })
    assert res.status_code == 404
