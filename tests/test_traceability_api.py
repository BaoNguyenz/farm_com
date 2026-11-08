"""
Integration test suite for VietGAP Food Safety & Traceability RESTful Endpoints.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.commander import CommanderAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_api_compliance_audit():
    resp = client.get("/api/v1/traceability/compliance-audit")
    assert resp.status_code == 200
    data = resp.json()

    assert data["farm_id"] == "farm-01"
    assert "overall_compliance_score" in data
    assert "compliance_tier" in data
    assert data["water_safety_passed"] is True
    assert data["zones_ready_for_harvest_count"] > 0


def test_api_treatment_logging():
    payload = {
        "zone_id": "Z_0_0",
        "substance_name": "Trichoderma asperellum",
        "substance_type": "bio_fungicide",
        "dosage_per_ha": 3.0,
        "phi_days": 1.0,
    }
    resp = client.post("/api/v1/traceability/treatment/log", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["zone_id"] == "Z_0_0"
    assert data["substance_name"] == "Trichoderma asperellum"
    assert data["phi_days_required"] == 1.0


def test_api_treatment_logging_not_found():
    payload = {
        "zone_id": "NON_EXISTENT_ZONE",
        "substance_name": "Bio Neem",
    }
    resp = client.post("/api/v1/traceability/treatment/log", json=payload)
    assert resp.status_code == 404


def test_api_mint_batch_passport():
    payload = {
        "zone_id": "Z_0_1",
        "weight_kg": 150.0,
    }
    resp = client.post("/api/v1/traceability/batch/passport", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert "VGAP-" in data["batch_id"]
    assert data["weight_kg"] == 150.0
    assert len(data["digital_signature_hash"]) == 64
    assert "https://trace.farm.vn/verify/" in data["qr_payload"]


def test_api_water_quality_profile():
    resp = client.get("/api/v1/traceability/water-quality")
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_compliant"] is True
    assert "TCVN" in data["standard"]
    assert "e_coli_cfu_per_100ml" in data["parameters"]


def test_commander_phi_quarantine_veto():
    agronomist = AgronomistAgent()
    irrigation = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agronomist, irrigation, market)

    proposal = {
        "action_type": "harvest_crop",
        "action_domain": "economics",
        "zone_id": "Z_0_0",
        "crop": "Strawberries",
    }

    # Context indicates active PHI residue with 48h remaining
    context = {
        "tariff_tier": "normal",
        "phi_cleared": False,
        "phi_remaining_hours": 48.0,
    }

    debate = commander.arbitrate_debate(proposal, context)
    assert debate.consensus_verdict == "rejected"
    assert "VIETGAP PHI VETO" in debate.resolution_notes
