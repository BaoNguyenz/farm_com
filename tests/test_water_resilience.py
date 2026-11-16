"""
Integration and Agent Test Suite for Water Resilience, Rainwater Harvesting & Solar RO Desalination.
"""
import pytest
from fastapi.testclient import TestClient

from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.core.twin_state import create_default_farm
from backend.main import app

client = TestClient(app)


@pytest.mark.anyio
async def test_irrigation_agent_water_resilience_integration() -> None:
    agent = IrrigationAgent()
    farm = create_default_farm()

    opinion = await agent.evaluate(farm)
    assert opinion.agent_id == "agent_irrigation"
    assert "rainwater_harvesting" in opinion.data_points
    assert "salinity_hazard" in opinion.data_points

    rainwater = opinion.data_points["rainwater_harvesting"]
    assert "cistern_capacity_liters" in rainwater
    assert "current_storage_liters" in rainwater


def test_irrigation_agent_salinity_veto() -> None:
    agent = IrrigationAgent()

    # Direct raw groundwater with 1400 ppm TDS on sensitive Strawberries
    veto_vote = agent.vote_on_proposal(
        proposal={"action_type": "irrigate_raw_groundwater", "action_domain": "irrigation"},
        context={"water_tds_ppm": 1400.0, "crop_type": "Strawberries", "ro_desalinated": False},
    )
    assert veto_vote.vote_choice == "REJECT"
    assert "SALINITY VETO" in veto_vote.rationale

    # Desalinated RO water is authorized
    approve_vote = agent.vote_on_proposal(
        proposal={"action_type": "irrigate_ro_permeate", "action_domain": "irrigation"},
        context={"water_tds_ppm": 20.0, "crop_type": "Strawberries", "ro_desalinated": True},
    )
    assert approve_vote.vote_choice == "APPROVE"


def test_market_agent_solar_ro_economics_and_voting() -> None:
    market = MarketAgent()

    # Solar RO economics calculation
    econ = market.evaluate_solar_desalination_economics(
        permeate_m3=5.0,
        solar_available_kw=2.5,
    )
    assert econ["is_solar_powered"] is True
    assert econ["energy_cost_vnd"] == 0.0
    assert econ["net_savings_vnd"] > 100000.0

    # Solar powered RO run is approved
    solar_vote = market.vote_on_proposal(
        proposal={"action_type": "run_desalination_batch"},
        context={"is_solar_powered": True, "solar_available_kw": 2.5},
    )
    assert solar_vote.vote_choice == "APPROVE"
    assert "surplus power" in solar_vote.rationale.lower()

    # Peak tariff without solar is vetoed
    peak_grid_vote = market.vote_on_proposal(
        proposal={"action_type": "run_desalination_batch"},
        context={"is_solar_powered": False, "solar_available_kw": 0.0, "tariff_tier": "peak"},
    )
    assert peak_grid_vote.vote_choice == "REJECT"
    assert "RO ECONOMIC VETO" in peak_grid_vote.rationale


def test_api_water_resilience_telemetry() -> None:
    res = client.get("/api/v1/water-resilience/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert "resilience_status" in data
    assert "rainwater_cistern" in data
    assert "solar_desalination" in data
    assert data["rainwater_cistern"]["capacity_liters"] >= 100000.0
    assert "TFC 4040" in data["solar_desalination"]["membrane_type"]


def test_api_harvest_runoff() -> None:
    payload = {
        "rainfall_mm": 15.0,
        "duration_hours": 2.0,
        "raw_turbidity_ntu": 40.0,
    }
    res = client.post("/api/v1/water-resilience/harvest-runoff", json=payload)
    assert res.status_code == 200
    report = res.json()
    assert report["rainfall_mm"] == 15.0
    assert report["gross_catchment_volume_liters"] > 10000.0
    assert report["first_flush_diverted_liters"] > 0.0
    assert report["net_harvested_liters"] > 0.0
    assert report["water_quality"]["irrigation_ready"] is True


def test_api_run_solar_desalination() -> None:
    payload = {
        "feed_tds_ppm": 2100.0,
        "feed_volume_m3": 3.5,
        "solar_available_kw": 2.4,
        "target_pressure_bar": 14.5,
        "use_erd": True,
    }
    res = client.post("/api/v1/water-resilience/run-desalination", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "active_desalination"
    assert data["permeate_water"]["tds_ppm"] <= 30.0
    assert data["metrics"]["salt_rejection_pct"] >= 99.0
    assert data["metrics"]["recovery_ratio_pct"] == 70.0
    assert data["total_permeate_m3"] > 0.0


def test_api_withdraw_rainwater() -> None:
    payload = {"volume_liters": 2500.0}
    res = client.post("/api/v1/water-resilience/withdraw-rainwater", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["requested_liters"] == 2500.0
    assert data["withdrawn_liters"] == 2500.0
    assert "remaining_storage_liters" in data
