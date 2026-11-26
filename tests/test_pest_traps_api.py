"""
Integration test suite for Smart Optical-Pheromone Pest Traps REST API & Agent Council.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_get_pest_traps_telemetry():
    """Verify GET /api/v1/pest-traps/telemetry returns plume, catch audit, and ROI."""
    response = client.get("/api/v1/pest-traps/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert data["network_status"] == "ACTIVE_OPTICAL_MONITORING"
    assert "plume_dispersion" in data
    assert data["plume_dispersion"]["effective_attraction_range_m"] > 0.0
    assert "population_audit" in data
    assert "ipm_audit" in data
    assert data["economics"]["is_profitable"] is True


def test_post_simulate_pheromone_plume():
    """Verify POST /api/v1/pest-traps/simulate-plume computes Gaussian dispersion."""
    payload = {
        "species": "tuta_absoluta",
        "ambient_temp_c": 24.0,
        "wind_speed_m_s": 1.5,
        "solar_irradiance_w_m2": 0.0,
    }
    response = client.post("/api/v1/pest-traps/simulate-plume", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["species"] == "tuta_absoluta"
    assert res["stability_class"] == "F"
    assert res["recommended_dispensers_per_ha"] >= 4


def test_post_record_catch_threshold_alert():
    """Verify POST /api/v1/pest-traps/record-catch triggers Economic Threshold alert."""
    payload = {
        "species": "spodoptera_litura",
        "cumulative_pdd": 365.0,
        "catches": [
            {"trap_id": "TRAP-01", "species": "spodoptera_litura", "raw_count": 8, "edge_ai_confidence": 0.95},
            {"trap_id": "TRAP-02", "species": "spodoptera_litura", "raw_count": 6, "edge_ai_confidence": 0.91},
        ],
    }
    response = client.post("/api/v1/pest-traps/record-catch", json=payload)
    assert response.status_code == 200
    res = response.json()

    assert res["mean_moths_per_trap_night"] == 7.0
    assert res["alert_level"] == "economic_threshold_exceeded"
    assert "TRICHOGRAMMA" in res["recommended_intervention"]


def test_agent_council_debate_on_pheromone_ipm():
    """Verify Agronomist IPM veto on unnecessary chemical spray and Market endorsement."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    proposal = {"action_type": "pheromone_disruption", "action_domain": "ipm"}

    # Below Economic Threshold with chemical spray subtype -> Agronomist veto
    spray_ctx = {"mean_moths_per_trap_night": 2.0, "economic_threshold": 5.0, "action_subtype": "chemical_spray"}
    veto = agronomist.vote_on_proposal(proposal=proposal, context=spray_ctx)
    assert veto.vote.lower() in ("reject", "veto")
    assert "IPM THRESHOLD VETO" in veto.rationale

    # Pheromone disruption endorsement
    ipm_ctx = {"mean_moths_per_trap_night": 6.5, "economic_threshold": 5.0}
    agro_ok = agronomist.vote_on_proposal(proposal=proposal, context=ipm_ctx)
    market_ok = market.vote_on_proposal(proposal=proposal, context=ipm_ctx)
    assert agro_ok.vote.lower() in ("approve", "accept")
    assert market_ok.vote.lower() in ("approve", "accept")
