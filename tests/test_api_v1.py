"""
Unit tests for v1 RESTful API Endpoints (Task 5.1)
Tests farm state, zone queries, simulation controller, council debate, and audit ledger.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_farm_state_and_dimensions(client):
    # Test state retrieval
    res = client.get("/api/v1/farm/state")
    assert res.status_code == 200
    data = res.json()
    assert "farm_id" in data
    assert "zones" in data
    assert "current_weather" in data
    assert "action_history" in data

    # Test include_history=False
    res_no_hist = client.get("/api/v1/farm/state?include_history=false")
    assert res_no_hist.status_code == 200
    assert "action_history" not in res_no_hist.json()

    # Test dimensions
    res_dim = client.get("/api/v1/farm/dimensions")
    assert res_dim.status_code == 200
    dim_data = res_dim.json()
    assert dim_data["grid_width"] >= 3
    assert dim_data["grid_height"] >= 3
    assert dim_data["total_zones"] == dim_data["grid_width"] * dim_data["grid_height"]
    assert dim_data["total_area_m2"] > 0


def test_get_zones_filtering_and_detail(client):
    # Query all zones
    res_all = client.get("/api/v1/farm/zones")
    assert res_all.status_code == 200
    all_zones = res_all.json()
    assert len(all_zones) > 0

    # Filter by moisture
    res_dry = client.get("/api/v1/farm/zones?max_moisture=50.0")
    assert res_dry.status_code == 200
    for z in res_dry.json():
        assert z["soil_moisture_pct"] <= 50.0

    # Zone detail & neighborhood topology
    sample_zone_id = all_zones[0]["id"]
    res_detail = client.get(f"/api/v1/farm/zones/{sample_zone_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == sample_zone_id
    assert "spatial_topology" in detail
    assert "von_neumann_neighbors" in detail["spatial_topology"]
    assert "moore_neighbors" in detail["spatial_topology"]

    # 404 for invalid zone
    res_not_found = client.get("/api/v1/farm/zones/Z_999_999")
    assert res_not_found.status_code == 404


def test_simulation_tick_and_weather_injection(client):
    # Step simulation
    step_res = client.post("/api/v1/simulation/tick", json={"hours": 2.5, "rain_mm": 5.0})
    assert step_res.status_code == 200
    step_data = step_res.json()
    assert step_data["status"] == "success"
    assert step_data["elapsed_hours"] == 2.5

    # Inject weather
    inject_res = client.post("/api/v1/simulation/weather", json={
        "temp_c": 32.5,
        "humidity_percent": 85.0,
        "solar_radiation_mj": 22.0,
        "wind_speed_ms": 3.2,
        "precipitation_mm": 12.0
    })
    assert inject_res.status_code == 200
    w_data = inject_res.json()["weather"]
    assert w_data["temp_c"] == 32.5
    assert w_data["humidity_percent"] == 85.0

    # Reset simulation
    reset_res = client.post("/api/v1/simulation/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "success"


def test_council_convene_and_custom_debate(client):
    # Convene council
    convene_res = client.post("/api/v1/council/convene")
    assert convene_res.status_code == 200
    verdict = convene_res.json()
    assert "opinions" in verdict
    assert "debate_rounds" in verdict
    assert "executive_summary" in verdict
    assert len(verdict["opinions"]) == 3

    # Arbitrate custom proposal debate
    debate_res = client.post("/api/v1/council/debate", json={
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "critical",
        "parameters": {"volume_mm": 15.0}
    })
    assert debate_res.status_code == 200
    debate_round = debate_res.json()
    assert "consensus_verdict" in debate_round
    assert "weighted_score" in debate_round
    assert len(debate_round["votes"]) == 3

    # Council history
    history_res = client.get("/api/v1/council/history")
    assert history_res.status_code == 200
    assert len(history_res.json()) >= 1


def test_audit_dispatch_and_ledger_verification(client):
    # Manual dispatch
    dispatch_res = client.post("/api/v1/audit/dispatch", json={
        "action_type": "irrigate_zone",
        "zone_id": "Z_0_0",
        "parameters": {"volume_mm": 20.0},
        "agent_name": "TestInspector"
    })
    assert dispatch_res.status_code == 200
    disp_data = dispatch_res.json()
    assert disp_data["status"] == "executed"
    assert disp_data["receipt"]["action_type"] == "irrigate_zone"

    # Query audit ledger
    ledger_res = client.get("/api/v1/audit/ledger?limit=10")
    assert ledger_res.status_code == 200
    ledger = ledger_res.json()
    assert len(ledger) > 0
    assert any(r["agent_name"] == "TestInspector" for r in ledger)

    # Verify cryptographic integrity
    verify_res = client.get("/api/v1/audit/verify")
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["is_valid"] is True
    assert v_data["algorithm"] == "SHA-256"
