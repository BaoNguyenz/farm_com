"""
Integration test suite for Microgrid Energy Management RESTful Endpoints.
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_api_microgrid_status():
    resp = client.get("/api/v1/microgrid/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "online"
    assert "solar_pv" in data
    assert "battery_bess" in data
    assert data["solar_pv"]["installed_capacity_kwp"] == 25.0
    assert 0.0 <= data["battery_bess"]["current_soc"] <= 1.0


def test_api_microgrid_dispatch_solar_self_consumption():
    payload = {
        "load_kw": 5.0,
        "irradiance_w_m2": 750.0,
        "ambient_temp_c": 25.0,
        "hour_of_day": 12,
        "grid_available": True,
        "duration_hours": 1.0,
    }
    resp = client.post("/api/v1/microgrid/dispatch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["solar_power_generated_kw"] > 5.0
    assert data["solar_used_directly_kw"] == 5.0
    assert data["grid_imported_kw"] == 0.0
    assert data["carbon_avoided_kg_co2e"] > 0.0


def test_api_microgrid_dispatch_peak_shaving():
    payload = {
        "load_kw": 7.0,
        "irradiance_w_m2": 0.0,
        "ambient_temp_c": 26.0,
        "hour_of_day": 18,  # Peak tariff hour
        "grid_available": True,
        "duration_hours": 1.0,
    }
    resp = client.post("/api/v1/microgrid/dispatch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["mode"] == "peak_shaving"
    assert data["tariff_tier"] == "peak"
    assert data["battery_discharged_kw"] > 0.0
    assert data["solar_savings_vnd"] > 0.0


def test_api_microgrid_dispatch_islanded_emergency():
    payload = {
        "load_kw": 10.0,
        "irradiance_w_m2": 500.0,
        "ambient_temp_c": 28.0,
        "hour_of_day": 14,
        "grid_available": False,  # Blackout
        "duration_hours": 1.0,
    }
    resp = client.post("/api/v1/microgrid/dispatch", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["mode"] == "islanded_emergency"
    assert data["grid_imported_kw"] == 0.0


def test_api_microgrid_tariffs():
    resp = client.get("/api/v1/microgrid/tariffs")
    assert resp.status_code == 200
    data = resp.json()

    assert data["currency"] == "VND"
    assert "off_peak" in data["tariffs"]
    assert "normal" in data["tariffs"]
    assert "peak" in data["tariffs"]
    assert data["tariffs"]["peak"]["rate_vnd_per_kwh"] > data["tariffs"]["off_peak"]["rate_vnd_per_kwh"]
