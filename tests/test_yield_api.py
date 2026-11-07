"""
Integration test suite for Crop Yield Forecasting & Harvest Logistics RESTful Endpoints.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_api_farm_yield_forecast():
    resp = client.get("/api/v1/yield/forecast")
    assert resp.status_code == 200
    data = resp.json()

    assert data["farm_id"] == "farm-01"
    assert data["total_farm_expected_yield_tons"] > 0.0
    assert 0.0 <= data["average_maturity_pct"] <= 100.0
    assert len(data["zone_forecasts"]) > 0
    assert "logistics_plan" in data


def test_api_zone_monte_carlo_simulation():
    payload = {
        "zone_id": "Z_0_0",
        "simulation_runs": 150,
        "ambient_temp_c": 23.5,
    }
    resp = client.post("/api/v1/yield/zone-simulation", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["zone_id"] == "Z_0_0"
    assert data["expected_yield_t_ha"] > 0.0
    mc = data["monte_carlo_metrics"]
    assert mc["p10_pessimistic_t_ha"] <= mc["p50_median_t_ha"]
    assert mc["p50_median_t_ha"] <= mc["p90_optimistic_t_ha"]


def test_api_zone_monte_carlo_not_found():
    payload = {
        "zone_id": "NON_EXISTENT_ZONE_XYZ",
        "simulation_runs": 100,
    }
    resp = client.post("/api/v1/yield/zone-simulation", json=payload)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_api_harvest_logistics_schedule():
    resp = client.get("/api/v1/yield/harvest-schedule")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_expected_yield_kg"] > 0.0
    assert data["total_crates_needed"] > 0
    assert data["labor_worker_shifts_needed"] > 0
    assert data["cold_storage_volume_m3"] > 0.0
    assert data["post_harvest_precooling_load_kwh"] > 0.0
