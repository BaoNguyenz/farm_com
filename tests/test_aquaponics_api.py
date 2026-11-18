"""
Integration and Agent Test Suite for Recirculating Aquaponics REST Endpoints and Multi-Agent Debate.
"""
from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.aquaponics_hydroponics import BaseChemical
from backend.main import app

client = TestClient(app)


def test_api_aquaponics_telemetry():
    """Verify GET /api/v1/aquaponics/telemetry endpoint."""
    response = client.get("/api/v1/aquaponics/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["system_id"] == "AQUAPONICS_FACILITY_01"
    assert data["total_water_volume_m3"] == 18.5
    assert "fish_tank" in data
    assert "biofilter" in data
    assert "hydroponics" in data
    assert data["total_fish_biomass_kg"] > 0
    assert data["total_crop_heads"] == 1000


def test_api_aquaponics_feed_batch():
    """Verify POST /api/v1/aquaponics/feed-batch endpoint."""
    payload = {
        "feed_kg": 0.8,
        "crude_protein_pct": 32.0,
    }
    response = client.post("/api/v1/aquaponics/feed-batch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "feed_administered"
    assert data["feed_kg"] == 0.8
    assert data["fish_biomass_kg"] > 200.0
    assert data["current_tan_mg_l"] > 0.0


def test_api_aquaponics_buffer_alkalinity():
    """Verify POST /api/v1/aquaponics/buffer-alkalinity endpoint."""
    payload = {
        "chemical": BaseChemical.POTASSIUM_BICARBONATE.value,
        "target_alkalinity_mg_l": 100.0,
    }
    response = client.post("/api/v1/aquaponics/buffer-alkalinity", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chemical"] == BaseChemical.POTASSIUM_BICARBONATE.value
    assert data["expected_alkalinity_after_mg_l"] == 100.0
    assert "Potassium (K+)" in data["rationale"]


def test_api_aquaponics_simulate_cycle():
    """Verify POST /api/v1/aquaponics/simulate-cycle endpoint."""
    payload = {
        "hours": 2.0,
        "feed_input_kg": 0.5,
        "par_umol_m2_s": 420.0,
        "supplementary_aeration": True,
    }
    response = client.post("/api/v1/aquaponics/simulate-cycle", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["water_flow_rate_m3_h"] == 3.5
    assert data["system_health_score"] >= 75.0


def test_agronomist_aquaponics_audit():
    """Verify AgronomistAgent aquaponics water chemistry audit."""
    agent = AgronomistAgent()
    audit = agent.audit_aquaponic_water_chemistry()
    assert "telemetry" in audit
    assert "ecosystem_status" in audit
    assert "system_health_score" in audit
    assert audit["system_health_score"] >= 80.0


def test_agronomist_aquaponics_vetoes():
    """Verify AgronomistAgent debate vetoes on fish tank hypoxia and copper spray."""
    agronomist = AgronomistAgent()

    # Hypoxia veto when fish tank DO < 5.0
    vote_aeration = agronomist.vote_on_proposal(
        proposal={"action_type": "curtail_aerator", "urgency": "normal"},
        context={"fish_tank_do_mg_l": 4.2},
    )
    assert vote_aeration.vote_choice == "REJECT"
    assert "HYPOXIA VETO" in vote_aeration.rationale

    # Toxic copper fungicide veto in aquaponics
    vote_copper = agronomist.vote_on_proposal(
        proposal={"action_type": "copper_spray", "urgency": "high"},
        context={"is_aquaponics": True},
    )
    assert vote_copper.vote_choice == "REJECT"
    assert "AQUAPONICS TOXICITY VETO" in vote_copper.rationale


def test_market_aquaponics_dual_harvest():
    """Verify MarketAgent dual-harvest economic assessment and vote endorsement."""
    market = MarketAgent()

    econ = market.evaluate_aquaponics_dual_harvest_economics(
        fish_biomass_kg=225.0,
        crop_heads=1000,
        crop_type="Butterhead Lettuce",
    )
    assert econ["fish_revenue_vnd"] == 225.0 * 75000.0  # 16,875,000 VND
    assert econ["crop_revenue_vnd"] == 1000 * 12000.0   # 12,000,000 VND
    assert econ["total_gross_revenue_vnd"] == 28875000.0
    assert econ["net_margin_vnd"] > 0
    assert econ["roi_ratio"] > 1.0

    # Debate endorsement
    vote_harvest = market.vote_on_proposal(
        proposal={"action_type": "aquaponics_harvest", "urgency": "normal"},
        context={},
    )
    assert vote_harvest.vote_choice == "APPROVE"
    assert "dual-harvest" in vote_harvest.rationale
