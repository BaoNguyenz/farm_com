"""
Integration test suite for Anaerobic Digestion & Biogas Micro-CHP REST API and Agent Reasoning.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.biogas_digestion import FeedstockType
from backend.main import app

client = TestClient(app)


def test_api_biogas_telemetry() -> None:
    response = client.get("/api/v1/biogas-cogen/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "digester" in data
    assert "chp_cogeneration" in data
    assert "digestate_valorization" in data
    assert data["digester"]["daily_biogas_m3"] > 0.0
    assert data["chp_cogeneration"]["electricity_generated_kwh"] > 0.0


def test_api_feed_anaerobic_digester() -> None:
    payload = {
        "feedstock": FeedstockType.CO_DIGESTION_MIX.value,
        "feed_mass_kg_day": 220.0,
        "operating_temp_c": 37.0,
        "retention_days": 25.0,
    }
    response = client.post("/api/v1/biogas-cogen/feed-digester", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["feedstock"] == FeedstockType.CO_DIGESTION_MIX.value
    assert data["daily_biogas_m3"] > 0.0
    assert data["daily_methane_m3"] > 0.0
    assert data["health_status"] == "stable_optimal"
    assert data["acidification_hazard"] is False


def test_api_simulate_chp_cogen() -> None:
    payload = {
        "biogas_volume_m3": 18.0,
        "methane_fraction_pct": 62.0,
        "parasitic_heat_kwh": 10.0,
    }
    response = client.post("/api/v1/biogas-cogen/simulate-chp", json=payload)
    assert response.status_code == 200
    cogen = response.json()
    assert cogen["electricity_generated_kwh"] > 30.0
    assert cogen["heat_recovered_kwh"] > 50.0
    assert cogen["heat_to_greenhouse_aquaponics_kwh"] > 0.0
    assert cogen["scrubbed_co2_kg"] > 25.0


def test_api_fractionate_digestate() -> None:
    payload = {
        "digestate_effluent_liters": 600.0,
        "digester_temp_c": 37.0,
    }
    response = client.post("/api/v1/biogas-cogen/fractionate-digestate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["solid_fraction_kg"] > 50.0
    assert data["liquid_fraction_liters"] > 400.0
    assert data["liquid_n_ppm"] > 1000.0
    assert data["pasteurization_compliant"] is True


def test_agronomist_digestate_audit_and_pathogen_veto() -> None:
    agent = AgronomistAgent()

    # Digestate audit
    audit = agent.audit_digestate_organic_safety(
        vfa_tic_ratio=0.22,
        pasteurization_compliant=True,
        liquid_ec_ms_cm=6.5,
    )
    assert audit["is_safe_for_application"] is True
    assert audit["prescribed_dilution_ratio"] == "1:10"

    # Pathogen unpasteurized veto
    vote_unpasteurized = agent.vote_on_proposal(
        proposal={"domain": "agronomy", "action_type": "apply_digestate", "urgency": "medium"},
        context={"pasteurization_compliant": False},
    )
    assert vote_unpasteurized.vote_choice == "REJECT"
    assert "PATHOGEN BIOSECURITY VETO" in vote_unpasteurized.rationale

    # Sour digester acid veto
    vote_sour = agent.vote_on_proposal(
        proposal={"domain": "agronomy", "action_type": "apply_digestate", "urgency": "medium"},
        context={"pasteurization_compliant": True, "vfa_tic_ratio": 0.48},
    )
    assert vote_sour.vote_choice == "REJECT"
    assert "SOUR DIGESTATE VETO" in vote_sour.rationale


def test_market_agent_biogas_cogen_roi_and_endorsement() -> None:
    agent = MarketAgent()

    savings = agent.evaluate_circular_biogas_savings(
        elec_kwh=35.0,
        heat_kwh=55.0,
        solid_compost_kg=85.0,
        scrubbed_co2_kg=28.0,
    )
    assert savings["total_circular_revenue_vnd"] > 400000.0
    assert savings["is_profitable"] is True

    vote = agent.vote_on_proposal(
        proposal={"domain": "energy", "action_type": "run_chp_cogen", "urgency": "normal"},
        context={},
    )
    assert vote.vote_choice == "APPROVE"
    assert "biogas chp cogeneration" in vote.rationale.lower()
