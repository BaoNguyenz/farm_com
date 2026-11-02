"""
Unit tests for Carbon-aware Market Agent calculations and
Commander biosecurity pathology veto arbitration in the Agent Council.
"""

from backend.agents.market import MarketAgent
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.commander import CommanderAgent
from backend.core.twin_state import create_default_farm


def test_market_agent_carbon_cost_estimation():
    agent = MarketAgent()
    res = agent.estimate_pumping_cost(water_volume_liters=10000.0, tier="normal")

    assert "scope2_emissions_kg_co2e" in res
    assert "carbon_tax_liability_vnd" in res
    assert res["energy_kwh"] > 0.0
    assert res["scope2_emissions_kg_co2e"] > 0.0
    assert abs(res["scope2_emissions_kg_co2e"] - res["energy_kwh"] * 0.7221) < 0.01


def test_commander_biosecurity_veto_arbitration():
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    proposal = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "medium",
        "total_liters": 2500.0
    }
    context = {
        "tariff_tier": "normal",
        "weather": {"humidity_percent": 92.0}
    }

    round_res = commander.arbitrate_debate(proposal, context)
    assert round_res.consensus_verdict == "rejected"
    assert "BIOSECURITY VETO" in round_res.resolution_notes


def test_commander_emergency_bypasses_biosecurity_veto():
    agro = AgronomistAgent()
    irri = IrrigationAgent()
    market = MarketAgent()
    commander = CommanderAgent(agro, irri, market)

    proposal = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "critical",
        "total_liters": 2500.0
    }
    context = {
        "tariff_tier": "normal",
        "weather": {"humidity_percent": 92.0}
    }

    round_res = commander.arbitrate_debate(proposal, context)
    assert round_res.consensus_verdict == "approved"
    assert "approved" in round_res.resolution_notes.lower() or "passed" in round_res.resolution_notes.lower()


def test_market_agent_evaluates_farm_carbon():
    farm = create_default_farm(width=2, height=2)
    market = MarketAgent()
    import asyncio
    opinion = asyncio.run(market.evaluate(farm))

    assert "grid_carbon_intensity_kg_kwh" in opinion.data_points
    assert opinion.data_points["grid_carbon_intensity_kg_kwh"] == 0.7221
