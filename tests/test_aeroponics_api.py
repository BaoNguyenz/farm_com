"""
Integration test suite for Vertical Aeroponics & LED Photobiology REST API & Agent Council.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_get_aeroponics_telemetry():
    """Verify GET /api/v1/aeroponics/telemetry returns chamber, LED spectrum, and ROI."""
    response = client.get("/api/v1/aeroponics/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert data["system_status"] == "VERTICAL_AEROPONICS_OPTIMAL"
    assert data["chamber"]["water_savings_vs_soil_pct"] == 95.0
    assert data["led_spectrum"]["phytochrome_pss"] > 0.72
    assert data["chamber_audit"]["is_chamber_optimal"] is True
    assert data["economics"]["is_profitable"] is True


def test_post_simulate_aeroponic_mist():
    """Verify POST /api/v1/aeroponics/simulate-mist evaluates root misting and ion uptake."""
    payload = {
        "atomizer_mode": "ultrasonic_piezo_1_7mhz",
        "root_chamber_temp_c": 22.0,
        "root_chamber_rh_pct": 93.0,
        "nitrate_ppm": 150.0,
        "potassium_ppm": 190.0,
    }
    response = client.post("/api/v1/aeroponics/simulate-mist", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["droplet_sauter_diameter_um"] < 20.0
    assert res["dissolved_oxygen_mg_l"] > 8.0
    assert res["chamber_status"] == "OPTIMAL_ULTRASONIC_MIST"


def test_post_tune_led_spectrum():
    """Verify POST /api/v1/aeroponics/tune-spectrum computes supplemental PPFD and PSS."""
    payload = {
        "recipe": "flowering_anthocyanin",
        "target_dli_mol_m2_day": 18.0,
        "solar_dli_mol_m2_day": 10.8,
        "photoperiod_hours": 10.0,
    }
    response = client.post("/api/v1/aeroponics/tune-spectrum", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["supplemental_dli_needed"] == 7.2
    assert res["supplemental_ppfd_umol_m2_s"] == 200.0
    assert res["shade_avoidance_risk"] is False


def test_agent_council_debate_on_aeroponics_and_led():
    """Verify Agronomist root hypoxia/shade-avoidance vetoes and Market endorsement."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    proposal = {"action_type": "aeroponics_mist", "action_domain": "cea"}

    # Root chamber overheating -> Agronomist veto
    hot_ctx = {"root_chamber_temp_c": 28.5, "shade_avoidance_risk": False}
    veto = agronomist.vote_on_proposal(proposal=proposal, context=hot_ctx)
    assert veto.vote.lower() in ("reject", "veto")
    assert "ROOT HYPOXIA VETO" in veto.rationale

    # Optimal condition -> both approve
    ok_ctx = {"root_chamber_temp_c": 21.0, "shade_avoidance_risk": False}
    assert agronomist.vote_on_proposal(proposal=proposal, context=ok_ctx).vote.lower() in ("approve", "accept")
    assert market.vote_on_proposal(proposal=proposal, context=ok_ctx).vote.lower() in ("approve", "accept")
