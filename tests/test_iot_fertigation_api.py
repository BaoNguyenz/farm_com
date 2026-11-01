"""
Integration tests for IoT LoRaWAN Gateway and Precision Fertigation REST APIs.
Tests uplink binary frame ingestion, gateway status, recipe retrieval,
water budget recharge, and canopy cooling status endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_lorawan_simulate_and_uplink_api(client):
    # 1. Simulate field node transmission
    sim_res = client.post("/api/v1/iot/lorawan/simulate", json={
        "x": 0,
        "y": 0,
        "soil_moisture_pct": 29.5,
        "soil_temp_c": 21.0,
        "soil_ec_us_cm": 1150.0,
        "battery_mv": 3650,
        "packet_type": "telemetry",
        "low_moisture_alert": True
    })
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["status"] == "simulated"
    assert sim_data["payload_bytes"] == 12
    hex_payload = sim_data["hex_payload"]
    assert len(hex_payload) == 24

    # 2. Ingest binary uplink via gateway endpoint
    uplink_res = client.post("/api/v1/iot/lorawan/uplink", json={
        "payload_hex": hex_payload,
        "dev_eui": "a84041000182a450",
        "rssi": -80,
        "snr": 8.5
    })
    assert uplink_res.status_code == 200
    uplink_data = uplink_res.json()
    assert uplink_data["status"] == "success"
    assert uplink_data["applied_to_twin"] is True
    assert uplink_data["packet"]["zone_id"] == "Z_0_0"
    assert abs(uplink_data["packet"]["soil_moisture_pct"] - 29.5) < 0.1


def test_lorawan_uplink_validation_errors(client):
    # Invalid hex string
    res_bad_hex = client.post("/api/v1/iot/lorawan/uplink", json={"payload_hex": "not_hex_data"})
    assert res_bad_hex.status_code == 400

    # Corrupted CRC (24 hex chars with modified byte)
    sim_res = client.post("/api/v1/iot/lorawan/simulate", json={
        "x": 1, "y": 1, "soil_moisture_pct": 50.0
    })
    corrupt_hex = sim_res.json()["hex_payload"][:-2] + "FF"
    res_crc = client.post("/api/v1/iot/lorawan/uplink", json={"payload_hex": corrupt_hex})
    assert res_crc.status_code == 422
    assert "CRC-8 verification failed" in res_crc.json()["detail"]


def test_gateway_status_api(client):
    res = client.get("/api/v1/iot/gateway/status")
    assert res.status_code == 200
    data = res.json()
    assert data["gateway_id"] == "gw-dalat-central-01"
    assert data["status"] == "online"
    assert "frequency_plan" in data
    assert data["managed_zones_count"] > 0


def test_fertigation_recipes_api(client):
    # Batch recipes
    res = client.get("/api/v1/fertigation/recipes?raw_water_ec=0.20&raw_water_ph=7.5")
    assert res.status_code == 200
    recipes = res.json()
    assert isinstance(recipes, list)
    assert len(recipes) > 0
    first = recipes[0]
    assert "target_ec_ms_cm" in first
    assert "tank_a_injection_ml_m3" in first
    assert "acid_injection_ml_m3" in first

    # Single zone recipe
    res_single = client.get(f"/api/v1/fertigation/recipes/{first['zone_id']}")
    assert res_single.status_code == 200
    assert res_single.json()["zone_id"] == first["zone_id"]

    # Not found zone
    res_404 = client.get("/api/v1/fertigation/recipes/Z_99_99")
    assert res_404.status_code == 404


def test_water_budget_and_recharge_api(client):
    # Get budget report
    res = client.get("/api/v1/fertigation/water-budget")
    assert res.status_code == 200
    budget = res.json()
    assert "storage_percentage" in budget
    assert "rationing_tier" in budget
    assert "days_of_autonomy" in budget

    # Recharge reservoir
    res_rech = client.post("/api/v1/fertigation/water-budget/recharge", json={
        "elapsed_hours": 4.0,
        "precipitation_mm": 12.0
    })
    assert res_rech.status_code == 200
    rech_data = res_rech.json()
    assert rech_data["status"] == "recharged"
    assert "report" in rech_data


def test_canopy_cooling_status_api(client):
    res = client.get("/api/v1/fertigation/cooling/status")
    assert res.status_code == 200
    data = res.json()
    assert "assessment" in data
    assert "alert_level" in data["assessment"]
    assert "vpd_kpa" in data["assessment"]
    assert "dispatcher_action" in data
