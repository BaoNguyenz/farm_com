"""
Integration and Agent Test Suite for Biological Pest Control REST Endpoints and Agent Debate.
"""
from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.biocontrol import PredatorSpecies, PreySpecies
from backend.main import app

client = TestClient(app)


def test_api_biocontrol_telemetry():
    """Verify GET /api/v1/biocontrol/telemetry endpoint."""
    response = client.get("/api/v1/biocontrol/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert len(data["beneficial_agents_active"]) >= 2
    assert "spider_mite" in data["monitored_prey_species"]
    assert "phytoseiulus_persimilis" in data["available_predator_species"]


def test_api_biocontrol_simulate_predation():
    """Verify POST /api/v1/biocontrol/simulate-predation endpoint."""
    payload = {
        "initial_prey": 20.0,
        "initial_predator": 3.0,
        "days": 6,
        "temp_c": 25.0,
        "predator_species": PredatorSpecies.PHYTOSEIULUS_PERSIMILIS.value,
        "prey_species": PreySpecies.TWO_SPOTTED_SPIDER_MITE.value,
    }
    response = client.post("/api/v1/biocontrol/simulate-predation", json=payload)
    assert response.status_code == 200
    states = response.json()
    assert len(states) == 13  # 6 days with step 0.5 = 12 steps + 1 initial
    assert states[-1]["prey_density"] < states[0]["prey_density"]


def test_api_biocontrol_check_safety_clean_and_toxic():
    """Verify POST /api/v1/biocontrol/check-safety endpoint."""
    # Case A: Pristine
    res_clean = client.post("/api/v1/biocontrol/check-safety", json={"target_beneficial": "phytoseiulus_persimilis", "spray_history": []})
    assert res_clean.status_code == 200
    assert res_clean.json()["is_safe_to_release"] is True

    # Case B: Toxic pyrethroid spray 1 day ago
    res_toxic = client.post(
        "/api/v1/biocontrol/check-safety",
        json={
            "target_beneficial": "phytoseiulus_persimilis",
            "spray_history": [
                {
                    "ingredient_name": "deltamethrin",
                    "application_date_days_ago": 1.0,
                    "initial_dose_ppm": 12.5,
                }
            ],
        },
    )
    assert res_toxic.status_code == 200
    data_toxic = res_toxic.json()
    assert data_toxic["is_safe_to_release"] is False
    assert data_toxic["limiting_ingredient"] == "deltamethrin"
    assert data_toxic["required_waiting_days_remaining"] > 0.0


def test_api_biocontrol_plan_zone_and_manifest():
    """Verify POST /api/v1/biocontrol/plan-zone-release and manifest endpoints."""
    zone_payload = {
        "zone_id": "ZONE_STRAWBERRY_B",
        "canopy_area_m2": 600.0,
        "pest_density": 18.0,
        "target_pest": PreySpecies.TWO_SPOTTED_SPIDER_MITE.value,
        "beneficial_species": PredatorSpecies.PHYTOSEIULUS_PERSIMILIS.value,
        "use_drone": True,
    }
    res_zone = client.post("/api/v1/biocontrol/plan-zone-release", json=zone_payload)
    assert res_zone.status_code == 200
    plan = res_zone.json()
    assert plan["packages_required"] == 9
    assert plan["drone_hopper_flow_rate_per_sec"] > 0.0

    # Test multi-zone manifest
    manifest_payload = [
        {"zone_id": "ZONE_A", "canopy_area_m2": 400.0, "pest_density": 4.0},
        {"zone_id": "ZONE_B", "canopy_area_m2": 600.0, "pest_density": 18.0},
    ]
    res_manifest = client.post("/api/v1/biocontrol/plan-farm-manifest", json=manifest_payload)
    assert res_manifest.status_code == 200
    manifest = res_manifest.json()
    assert manifest["total_zones"] == 2
    assert manifest["total_canopy_area_m2"] == 1000.0


def test_agronomist_agent_biocontrol_audit():
    """Verify AgronomistAgent biological control audit method."""
    agent = AgronomistAgent()

    # Case 1: Blocked due to recent spray
    audit_blocked = agent.audit_biocontrol_safety_and_release(
        zone_id="ZONE_B",
        canopy_area_m2=500.0,
        pest_density=12.0,
        spray_history=[{"ingredient_name": "imidacloprid", "application_date_days_ago": 2.0, "initial_dose_ppm": 25.0}],
    )
    assert audit_blocked["release_authorized"] is False
    assert audit_blocked["release_plan"] is None

    # Case 2: Authorized with clean history
    audit_ok = agent.audit_biocontrol_safety_and_release(
        zone_id="ZONE_B",
        canopy_area_m2=500.0,
        pest_density=12.0,
        spray_history=[],
    )
    assert audit_ok["release_authorized"] is True
    assert audit_ok["release_plan"] is not None


def test_agent_debate_biocontrol_veto_and_endorsements():
    """Verify Agronomist and Market agent debate logic on biocontrol and pesticides."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    # Agronomist vetoes chemical pesticide when beneficials are established
    vote_pest = agronomist.vote_on_proposal(
        proposal={"action_type": "chemical_spray", "urgency": "urgent", "domain": "pest_management"},
        context={"beneficials_active": True},
    )
    assert vote_pest.vote_choice == "REJECT"
    assert "TOXICITY VETO" in vote_pest.rationale

    # Agronomist endorses macro-biologic release
    vote_bio = agronomist.vote_on_proposal(
        proposal={"action_type": "macro_biologic_release", "urgency": "normal", "domain": "pest_management"},
        context={},
    )
    assert vote_bio.vote_choice == "APPROVE"

    # Market agent vetoes chemical spray on export strawberries
    vote_market = market.vote_on_proposal(
        proposal={"action_type": "chemical_spray", "urgency": "normal"},
        context={"crop_type": "Strawberries", "export_grade": True},
    )
    assert vote_market.vote_choice == "REJECT"
    assert "MARKET EXPORT VETO" in vote_market.rationale


def test_market_agent_biocontrol_economics():
    """Verify MarketAgent cost-benefit analysis between biocontrol and chemicals."""
    market = MarketAgent()
    econ = market.evaluate_biocontrol_economics(
        canopy_area_m2=600.0,
        pest_density=16.0,
        crop_type="Strawberries",
    )
    assert econ["crop_type"] == "Strawberries"
    assert econ["organic_premium_preserved_vnd"] > 0
    assert econ["net_savings_vnd"] > 0
    assert econ["recommend_biocontrol"] is True
