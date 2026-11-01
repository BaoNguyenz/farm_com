"""
Unit tests for extended Agent Council behaviors:
- Reservoir-aware IrrigationAgent (budgeting, rationing, and empty tank veto)
- Thermal kinetics and pathology veto logic in AgronomistAgent
"""

import pytest
from backend.agents.irrigation import IrrigationAgent
from backend.agents.agronomist import AgronomistAgent
from backend.core.water_budget import WaterBudgetManager, ReservoirState
from backend.core.twin_state import create_default_farm


@pytest.mark.anyio
async def test_irrigation_agent_water_budget_integration():
    farm = create_default_farm(width=2, height=2)
    for z in farm.zones:
        z.soil_moisture_pct = 40.0  # Needs watering

    # Moderate deficit (30% storage) -> 70% rationing
    budget_mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=15000.0,
        emergency_reserve_liters=5000.0
    ))
    agent = IrrigationAgent(water_budget_mgr=budget_mgr)

    opinion = await agent.evaluate(farm)
    assert "water_budget" in opinion.data_points
    assert opinion.data_points["water_budget"]["rationing_tier"] == "moderate_deficit"
    assert "Reservoir storage: 30.0%" in opinion.reasoning


def test_irrigation_agent_veto_empty_reservoir():
    # Reservoir at 3,000 L (below 5,000 L emergency reserve)
    budget_mgr = WaterBudgetManager(ReservoirState(
        capacity_liters=50000.0,
        current_storage_liters=3000.0,
        emergency_reserve_liters=5000.0
    ))
    agent = IrrigationAgent(water_budget_mgr=budget_mgr)

    proposal_routine = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "medium",
        "total_liters": 1500.0
    }
    vote = agent.vote_on_proposal(proposal_routine, context={})
    assert vote.vote_choice == "REJECT"
    assert "critically empty" in vote.rationale.lower()

    # Emergency proposal bypasses veto
    proposal_emergency = {
        "action_type": "irrigate_plot_zones",
        "action_domain": "hydrology",
        "urgency": "critical",
        "total_liters": 1500.0
    }
    vote_emg = agent.vote_on_proposal(proposal_emergency, context={})
    assert vote_emg.vote_choice == "APPROVE"


@pytest.mark.anyio
async def test_agronomist_agent_heat_stress_evaluation():
    farm = create_default_farm(width=2, height=2)
    farm.current_weather.temp_c = 38.0
    farm.current_weather.humidity_percent = 25.0

    agent = AgronomistAgent()
    opinion = await agent.evaluate(farm)

    assert opinion.urgency == "critical"
    assert "extreme_thermal_shock" in str(opinion.data_points.get("heat_stress"))
    assert "fogging" in opinion.recommendation.lower() or "thermal shock" in opinion.recommendation.lower()


def test_agronomist_pathology_veto_high_humidity():
    agent = AgronomistAgent()
    proposal_irri = {
        "action_type": "irrigate_zone",
        "action_domain": "hydrology",
        "urgency": "low"
    }
    context = {"weather": {"humidity_percent": 90.0}}

    vote = agent.vote_on_proposal(proposal_irri, context)
    assert vote.vote_choice == "REJECT"
    assert "pathology veto" in vote.rationale.lower()
