"""
Integration test suite for Post-Harvest Produce Respiration & MAP REST API and Agent Reasoning.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.postharvest_map import PackagingFilmType
from backend.core.postharvest_respiration import PerishableCommodity
from backend.main import app

client = TestClient(app)


def test_api_postharvest_telemetry() -> None:
    response = client.get("/api/v1/postharvest/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "cold_room" in data
    assert "map_packaging" in data
    assert data["cold_room"]["r_o2_ml_kg_h"] > 0.0
    assert data["map_packaging"]["botrytis_inhibition_pct"] > 0.0


def test_api_evaluate_respiration() -> None:
    payload = {
        "commodity": PerishableCommodity.STRAWBERRIES.value,
        "storage_temp_c": 2.5,
        "ambient_rh_pct": 92.0,
        "o2_pct": 20.9,
        "co2_pct": 0.04,
        "elapsed_days_in_store": 1.0,
    }
    response = client.post("/api/v1/postharvest/evaluate-respiration", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["commodity"] == PerishableCommodity.STRAWBERRIES.value
    assert data["r_o2_ml_kg_h"] > 0.0
    assert data["remaining_shelf_life_days"] > 10.0
    assert data["freshness_index_score"] > 80.0


def test_api_design_map_package() -> None:
    payload = {
        "film_type": PackagingFilmType.MICRO_PERFORATED_PP.value,
        "fruit_mass_kg": 0.5,
        "package_area_m2": 0.04,
        "storage_temp_c": 2.0,
        "fruit_r_o2_ml_kg_h": 8.5,
    }
    response = client.post("/api/v1/postharvest/design-map-package", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["film_type"] == PackagingFilmType.MICRO_PERFORATED_PP.value
    assert 2.0 <= res["equilibrium_o2_pct"] <= 6.0
    assert 10.0 <= res["equilibrium_co2_pct"] <= 18.0
    assert res["botrytis_inhibition_pct"] >= 80.0
    assert res["package_status"] == "OPTIMAL_PRESERVATION_WINDOW"


def test_api_audit_cold_chain() -> None:
    temps = [2.0 + (0.4 if i % 2 == 0 else -0.2) for i in range(24)]
    payload = {
        "lot_id": "LOT_EXP_009",
        "hourly_temperatures_c": temps,
        "base_temp_c": 3.0,
        "max_allowable_degree_hours": 45.0,
    }
    response = client.post("/api/v1/postharvest/audit-cold-chain", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["lot_id"] == "LOT_EXP_009"
    assert data["total_transit_hours"] == 24.0
    assert data["cold_chain_breach"] is False
    assert data["quality_grade"] == "GRADE_AAA_PREMIUM"


def test_agronomist_cold_chain_audit_and_thermal_breach_veto() -> None:
    agent = AgronomistAgent()

    # Cold chain audit
    audit = agent.audit_postharvest_cold_chain(
        lot_id="LOT_001",
        quality_grade="GRADE_AAA_PREMIUM",
        cumulative_degree_hours=12.5,
        botrytis_inhibition_pct=88.0,
    )
    assert audit["is_export_cleared"] is True
    assert audit["disposition"] == "CLEAR_FOR_AIR_FREIGHT"

    # Thermal breach veto
    vote_breached = agent.vote_on_proposal(
        proposal={"domain": "postharvest", "action_type": "ship_export_batch", "urgency": "high"},
        context={"quality_grade": "GRADE_B_DOMESTIC_DOWNGRADE", "cumulative_degree_hours": 58.0},
    )
    assert vote_breached.vote_choice == "REJECT"
    assert "COLD-CHAIN BREACH VETO" in vote_breached.rationale


def test_market_agent_map_export_roi_and_endorsement() -> None:
    agent = MarketAgent()

    roi = agent.evaluate_map_export_premium(
        batch_mass_kg=500.0,
        quality_grade="GRADE_AAA_PREMIUM",
    )
    assert roi["export_premium_margin_vnd"] > 50000000.0  # > 50M VND export premium
    assert roi["is_export_viable"] is True

    vote = agent.vote_on_proposal(
        proposal={"domain": "packaging", "action_type": "map_packaging", "urgency": "normal"},
        context={},
    )
    assert vote.vote_choice == "APPROVE"
    assert "modified atmosphere packaging" in vote.rationale.lower()
