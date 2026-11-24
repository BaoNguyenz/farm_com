"""
Integration test suite for Solar Thermal Crop Dryer & Latent Heat PCM REST API.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_get_solar_dryer_telemetry():
    """Verify GET /api/v1/solar-dryer/telemetry returns coupled thermal, batch, and economic data."""
    response = client.get("/api/v1/solar-dryer/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert data["facility_status"] == "ONLINE_ACTIVE_DRYING"
    assert "thermal_system" in data
    assert data["thermal_system"]["collector_useful_heat_gain_w"] > 0.0
    assert "active_batch" in data
    assert data["active_batch"]["commodity"] == "strawberry_slices"
    assert "quality_audit" in data
    assert "economics" in data
    assert data["economics"]["is_profitable"] is True


def test_post_simulate_crop_drying():
    """Verify POST /api/v1/solar-dryer/simulate-drying calculates Page model moisture loss."""
    payload = {
        "commodity": "strawberry_slices",
        "elapsed_hours": 16.0,
        "chamber_air_temp_c": 48.0,
        "chamber_air_rh_pct": 20.0,
    }
    response = client.post("/api/v1/solar-dryer/simulate-drying", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["commodity"] == "strawberry_slices"
    assert res["elapsed_time_hours"] == 16.0
    assert res["moisture_wet_basis_pct"] < 90.0
    assert res["moisture_ratio_mr"] < 1.0
    assert res["water_activity_aw"] > 0.0
    assert res["vitamin_c_retention_pct"] > 60.0


def test_post_pcm_thermal_state():
    """Verify POST /api/v1/solar-dryer/pcm-status calculates thermal balances."""
    payload = {
        "current_pcm_temp_c": 45.0,
        "ambient_temp_c": 22.0,
        "ambient_rh_pct": 65.0,
        "solar_irradiance_w_m2": 800.0,
        "auxiliary_heat_available_w": 0.0,
        "hour_of_day": 12.0,
    }
    response = client.post("/api/v1/solar-dryer/pcm-status", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["collector_useful_heat_gain_w"] > 5000.0
    assert res["pcm_liquid_fraction"] > 0.0
    assert res["pcm_stored_energy_kwh"] > 0.0
    assert res["chamber_inlet_temp_c"] > 30.0


def test_post_audit_drying_quality():
    """Verify POST /api/v1/solar-dryer/audit-quality verifies biophysical safety thresholds."""
    payload = {
        "commodity": "strawberry_slices",
        "water_activity_aw": 0.54,
        "moisture_wb_pct": 11.2,
        "vitamin_c_retention_pct": 76.0,
        "chamber_temp_c": 48.0,
    }
    response = client.post("/api/v1/solar-dryer/audit-quality", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["is_microbiologically_safe"] is True
    assert res["quality_tier"] == "GRADE_AAA_EXPORT"


def test_agent_council_debate_on_solar_drying():
    """Verify Agronomist and Market agent votes on solar drying proposals."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    proposal = {"action_type": "solar_drying_batch", "action_domain": "postharvest"}

    # 1. Nominal batch: both approve
    nominal_ctx = {"chamber_air_temp_c": 48.0, "water_activity_aw": 0.55}
    agro_vote = agronomist.vote_on_proposal(proposal=proposal, context=nominal_ctx)
    market_vote = market.vote_on_proposal(proposal=proposal, context=nominal_ctx)

    assert agro_vote.vote.lower() in ("approve", "accept")
    assert market_vote.vote.lower() in ("approve", "accept")

    # 2. Overheated batch (>55°C): Agronomist issues thermal abuse veto
    overheat_ctx = {"chamber_air_temp_c": 62.0, "water_activity_aw": 0.45}
    veto_vote = agronomist.vote_on_proposal(proposal=proposal, context=overheat_ctx)

    assert veto_vote.vote.lower() in ("reject", "veto")
    assert "DRYING THERMAL ABUSE VETO" in veto_vote.rationale
