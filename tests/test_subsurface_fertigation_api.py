"""
Integration test suite for Subsurface Drip & Precision Fertigation REST API and Agent Reasoning.
"""

from fastapi.testclient import TestClient

from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.core.fertigation_solute import FertigationRecipe
from backend.core.irrigation_hydraulics import SoilTextureClass
from backend.main import app

client = TestClient(app)


def test_api_subsurface_telemetry() -> None:
    response = client.get("/api/v1/subsurface-fertigation/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "wetted_bulb" in data
    assert "fertigation_station" in data
    assert data["wetted_bulb"]["radial_width_cm"] > 0.0
    assert data["fertigation_station"]["measured_ec_ms_cm"] > 0.0


def test_api_simulate_wetted_bulb() -> None:
    payload = {
        "soil_type": "loam",
        "emitter_depth_cm": 20.0,
        "emitter_discharge_lph": 1.6,
        "application_duration_hours": 2.5,
        "initial_moisture": 0.20,
    }
    response = client.post("/api/v1/subsurface-fertigation/simulate-bulb", json=payload)
    assert response.status_code == 200
    bulb = response.json()
    assert bulb["depth_cm"] == 20.0
    assert bulb["radial_width_cm"] > 20.0
    assert bulb["vertical_height_cm"] > 20.0
    assert bulb["matric_suction_kpa"] > 0.0


def test_api_calculate_fertigation_dosing() -> None:
    payload = {
        "recipe": FertigationRecipe.FRUITING.value,
        "irrigation_flow_rate_lph": 1800.0,
        "measured_ec": 2.35,
        "measured_ph": 6.8,
    }
    response = client.post("/api/v1/subsurface-fertigation/mix-dosing", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["recipe"] == FertigationRecipe.FRUITING.value
    assert res["target_ec_ms_cm"] == 2.40
    assert res["stock_a_injection_lph"] > 0.0
    assert res["stock_b_injection_lph"] > 0.0
    assert res["acid_c_injection_lph"] > 0.0  # pH 6.8 > target 6.05 triggers acid injection


def test_api_compute_solute_transport_profile() -> None:
    payload = {
        "surface_ec": 2.4,
        "soil_depth_cm": 60.0,
        "pore_water_velocity_cm_h": 2.5,
        "elapsed_hours": 4.0,
    }
    response = client.post("/api/v1/subsurface-fertigation/solute-profile", json=payload)
    assert response.status_code == 200
    profile = response.json()
    assert len(profile) == 6
    assert profile[0]["depth_cm"] == 0.0
    assert profile[0]["solute_ec_ms_cm"] >= profile[-1]["solute_ec_ms_cm"]


def test_irrigation_agent_subsurface_audit_and_salinity_veto() -> None:
    agent = IrrigationAgent()

    # Audit vadose zone matric suction
    audit = agent.audit_subsurface_matric_tension("ZONE_0_0", 0.15, SoilTextureClass.LOAM)
    assert audit["zone_id"] == "ZONE_0_0"
    assert audit["matric_suction_kpa"] > 0.0
    assert audit["status"] in ("optimal_moisture", "mild_depletion", "critical_suction_stress")

    # Salinity veto when EC > 2.8 mS/cm
    vote_saline = agent.vote_on_proposal(
        proposal={"domain": "irrigation", "action_type": "sdi_fertigation_pulse", "urgency": "medium"},
        context={"measured_ec": 3.2},
    )
    assert vote_saline.vote_choice == "REJECT"
    assert "SALINITY VETO" in vote_saline.rationale

    # Approval when EC is safe
    vote_safe = agent.vote_on_proposal(
        proposal={"domain": "irrigation", "action_type": "sdi_fertigation_pulse", "urgency": "medium"},
        context={"measured_ec": 2.1},
    )
    assert vote_safe.vote_choice == "APPROVE"


def test_market_agent_subsurface_roi_and_endorsement() -> None:
    agent = MarketAgent()

    roi = agent.evaluate_subsurface_fertigation_roi(
        water_saved_m3=8.5,
        fertilizer_saved_kg=4.2,
        pumping_hours_avoided=1.5,
    )
    assert roi["total_daily_savings_vnd"] > 100000.0
    assert roi["is_cost_effective"] is True

    vote = agent.vote_on_proposal(
        proposal={"domain": "irrigation", "action_type": "subsurface_drip_pulse", "urgency": "low"},
        context={},
    )
    assert vote.vote_choice == "APPROVE"
    assert "subsurface fertigation" in vote.rationale.lower()
