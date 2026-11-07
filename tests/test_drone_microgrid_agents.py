"""
Unit tests for Microgrid-Aware Market Decisions & Drone-Assisted Agronomy in Agent Swarm.
"""

import asyncio

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.twin_state import create_default_farm


def test_market_agent_microgrid_arbitrage_and_vote():
    market = MarketAgent()

    # Peak hour arbitrage with high solar + battery
    arb_peak = market.evaluate_microgrid_arbitrage(solar_power_kw=8.0, battery_soc=0.70, hour=10.0)
    assert arb_peak["can_self_power"] is True
    assert arb_peak["strategy"] == "peak_shaving_discharge"
    assert arb_peak["hourly_cost_savings_vnd"] > 0

    # Off-peak grid charge recommendation
    arb_offpeak = market.evaluate_microgrid_arbitrage(solar_power_kw=0.0, battery_soc=0.20, hour=2.0)
    assert arb_offpeak["strategy"] == "off_peak_grid_bess_charge"

    # Vote on peak irrigation without microgrid -> REJECT
    proposal = {"action_type": "irrigation_pump", "urgency": "low"}
    vote_grid = market.vote_on_proposal(proposal, context={"tariff_tier": "peak", "battery_soc": 0.10})
    assert vote_grid.vote_choice == "REJECT"

    # Vote on peak irrigation WITH microgrid clean power -> APPROVE
    vote_microgrid = market.vote_on_proposal(proposal, context={"tariff_tier": "peak", "battery_soc": 0.85})
    assert vote_microgrid.vote_choice == "APPROVE"
    assert "Microgrid" in vote_microgrid.rationale


def test_agronomist_agent_drone_ingestion_and_evaluation():
    agronomist = AgronomistAgent()
    farm = create_default_farm()

    # Ingest synthetic drone survey with anomalies
    survey_data = {
        "status": "completed",
        "critical_anomalies": ["Zone Z_0_0: 3 chlorotic patches"],
        "zone_surveys": [
            {"zone_id": "Z_0_0", "chlorosis_hotspots": 3, "weed_pressure_score": 0.1},
            {"zone_id": "Z_0_1", "chlorosis_hotspots": 0, "weed_pressure_score": 0.6},
        ],
    }

    ingested = agronomist.ingest_drone_survey(survey_data)
    assert ingested["prescriptions_generated"] == 2
    actions = [p["action"] for p in ingested["prescriptions"]]
    assert "variable_rate_foliar_nitrogen" in actions
    assert "spot_organic_herbicide_micro_spray" in actions

    # Vote on drone spray proposal
    drone_proposal = {"action_type": "uav_drone_spot_spray", "action_domain": "agronomy"}
    vote = agronomist.vote_on_proposal(drone_proposal, context={})
    assert vote.vote_choice == "APPROVE"
    assert "UAV" in vote.rationale

    # Full evaluate run includes drone telemetry
    opinion = asyncio.run(agronomist.evaluate(farm))
    assert "drone_scouting" in opinion.data_points
    assert opinion.data_points["drone_scouting"]["drone_mission_status"] == "completed"
