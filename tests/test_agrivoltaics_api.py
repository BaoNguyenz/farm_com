"""
Integration and Agent Test Suite for Agrivoltaics REST Endpoints, Sun-Tracking, and Dynamic Crop Shading.
"""
from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.agrivoltaic_shading import AgrivoltaicOperationalMode
from backend.main import app

client = TestClient(app)


def test_api_agrivoltaics_telemetry():
    """Verify GET /api/v1/agrivoltaics/telemetry endpoint."""
    response = client.get("/api/v1/agrivoltaics/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["installed_capacity_kwp"] == 30.0
    assert "tracker_state" in data
    assert "canopy_microclimate" in data
    assert "active_mode" in data


def test_api_agrivoltaics_adjust_mode():
    """Verify POST /api/v1/agrivoltaics/adjust-mode endpoint."""
    payload = {"mode": AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING.value}
    response = client.post("/api/v1/agrivoltaics/adjust-mode", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "mode_updated"
    assert data["active_mode"] == AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING.value

    # Reset back to max electricity
    client.post("/api/v1/agrivoltaics/adjust-mode", json={"mode": AgrivoltaicOperationalMode.MAX_ELECTRICITY_YIELD.value})


def test_api_agrivoltaics_dispatch_shading_under_heatwave():
    """Verify POST /api/v1/agrivoltaics/dispatch endpoint overrides tilt for strawberry sunburn defense."""
    payload = {
        "day_of_year": 120,
        "local_hour": 12.0,
        "ambient_ghi_w_m2": 950.0,
        "canopy_temp_c": 33.8,  # > 30.5C heat stress threshold
        "crop_type": "Strawberries",
    }
    response = client.post("/api/v1/agrivoltaics/dispatch", json=payload)
    assert response.status_code == 200
    decision = response.json()
    assert decision["active_mode"] == AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING.value
    assert decision["commanded_tilt_deg"] == 0.0
    assert decision["crop_stress_mitigated"] is True
    assert decision["canopy_microclimate"]["leaf_temp_reduction_c"] > 1.5


def test_api_agrivoltaics_diurnal_profile():
    """Verify GET /api/v1/agrivoltaics/diurnal-profile endpoint."""
    response = client.get("/api/v1/agrivoltaics/diurnal-profile?day_of_year=120")
    assert response.status_code == 200
    profile = response.json()
    assert len(profile) == 13
    assert profile[6]["generated_power_kw"] > 0.0


def test_agronomist_agrivoltaics_audit_and_veto():
    """Verify AgronomistAgent audit method and debate veto on force_max_power under leaf burn."""
    agronomist = AgronomistAgent()

    # Audit under noon heatwave
    audit = agronomist.audit_agrivoltaic_canopy_welfare(
        canopy_temp_c=32.5,
        ambient_ghi_w_m2=900.0,
        crop_type="Strawberries",
    )
    assert audit["needs_defensive_shading"] is True
    assert audit["recommended_mode"] == AgrivoltaicOperationalMode.CROP_PROTECTIVE_SHADING.value

    # Debate veto when operator attempts to force max power during crop scald
    vote_force = agronomist.vote_on_proposal(
        proposal={"action_type": "force_max_power", "urgency": "high"},
        context={"canopy_temp_c": 33.0},
    )
    assert vote_force.vote_choice == "REJECT"
    assert "PHOTOINHIBITION VETO" in vote_force.rationale

    # Debate endorsement for protective shading
    vote_shade = agronomist.vote_on_proposal(
        proposal={"action_type": "crop_shading", "urgency": "urgent"},
        context={},
    )
    assert vote_shade.vote_choice == "APPROVE"


def test_market_agrivoltaics_tradeoff_and_endorsement():
    """Verify MarketAgent cost-benefit analysis between electricity revenue and crop protection."""
    market = MarketAgent()

    tradeoff = market.evaluate_agrivoltaic_shading_tradeoff(
        curtailed_pv_kwh=8.5,
        crop_area_m2=600.0,
        crop_type="Strawberries",
    )
    assert tradeoff["power_loss_vnd"] > 0
    assert tradeoff["crop_value_preserved_vnd"] > tradeoff["power_loss_vnd"]
    assert tradeoff["net_economic_benefit_vnd"] > 0
    assert tradeoff["recommend_shading"] is True

    # Debate endorsement
    vote_shade = market.vote_on_proposal(
        proposal={"action_type": "agrivoltaic_shade", "urgency": "normal"},
        context={},
    )
    assert vote_shade.vote_choice == "APPROVE"
    assert "agrivoltaic defensive shading" in vote_shade.rationale
