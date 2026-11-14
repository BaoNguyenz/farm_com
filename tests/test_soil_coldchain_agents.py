"""
Unit test suite for Soil Microbiome Leaching-Aware IrrigationAgent
and Cold-Chain Shelf-Life Economics MarketAgent.
"""
import asyncio

import pytest

from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.core.cold_chain import ColdChainEngine, ColdChamberState
from backend.core.soil_microbiome import SoilMicrobiomeEngine
from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherSnapshot


@pytest.fixture
def mock_farm() -> FarmDigitalTwin:
    zones = [
        PlotZone(
            id="Z_1_1",
            x=0,
            y=0,
            crop_type="Strawberries",
            growth_stage="fruiting",
            soil_moisture_pct=92.0,  # Saturated, leaching-prone and hypoxic
            canopy_temp_c=21.0,
            accumulated_gdd=350.0,
        ),
        PlotZone(
            id="Z_1_2",
            x=1,
            y=0,
            crop_type="Bell Pepper",
            growth_stage="vegetative",
            soil_moisture_pct=42.0,  # Needs irrigation
            canopy_temp_c=22.0,
            accumulated_gdd=120.0,
        ),
    ]
    weather = WeatherSnapshot(
        temp_c=24.0,
        humidity_percent=60.0,
        wind_speed_ms=2.0,
        solar_radiation_mj=18.0,
        precipitation_mm=0.0,
    )
    return FarmDigitalTwin(
        farm_id="farm-test-01",
        name="Highland Test Farm",
        latitude=11.94,
        longitude=108.45,
        zones=zones,
        current_weather=weather,
    )


def test_irrigation_agent_soil_leaching_evaluation(mock_farm: FarmDigitalTwin) -> None:
    soil_engine = SoilMicrobiomeEngine()
    agent = IrrigationAgent(soil_engine=soil_engine)

    opinion = asyncio.run(agent.evaluate(mock_farm))

    assert opinion.agent_id == "agent_irrigation"
    assert "soil_health_report" in opinion.data_points
    report = opinion.data_points["soil_health_report"]
    assert "average_soil_health_index" in report
    assert report["zones_with_hypoxia_risk_count"] >= 1


def test_irrigation_agent_leaching_veto() -> None:
    agent = IrrigationAgent()

    # Proposal to irrigate when target zone is already at 86% moisture (saturated)
    proposal = {
        "action_type": "irrigate_plot",
        "action_domain": "hydrology",
        "urgency": "low",
    }
    context = {
        "target_soil_moisture_pct": 86.0,
        "leaching_risk_tier": "critical_leaching",
    }

    vote = agent.vote_on_proposal(proposal, context)

    assert vote.vote_choice == "REJECT"
    assert "LEACHING & ROOT HYPOXIA VETO" in vote.rationale


def test_market_agent_cold_chain_inventory() -> None:
    cold_engine = ColdChainEngine()
    market = MarketAgent(cold_chain_engine=cold_engine)

    chambers = [
        ColdChamberState(
            chamber_id="CHAMBER-EXP",
            crop_type="Strawberries",
            stored_weight_kg=500.0,
            air_temp_c=16.0,  # Extreme thermal abuse
            relative_humidity_pct=70.0,
            ethylene_ppm=0.35,
            hours_in_storage=72.0,
        )
    ]

    audit = market.evaluate_cold_chain_inventory(chambers)
    assert audit["chambers_count"] == 1
    assert audit["expedited_sale_required"] is True

    record = audit["inventory_records"][0]
    assert record["quality_grade"] == "EXPEDITED_SALE_REQUIRED"
    assert record["adjusted_price_vnd"] < record["base_price_vnd"]
    assert record["expedited_dispatch"] is True


def test_market_agent_cold_chain_arbitrage_veto() -> None:
    market = MarketAgent()

    proposal = {
        "action_type": "defer_shipment_to_tomorrow",
        "action_domain": "logistics",
        "urgency": "low",
    }
    context = {
        "cold_chain_quality_grade": "EXPEDITED_SALE_REQUIRED",
        "remaining_shelf_life_days": 1.5,
    }

    vote = market.vote_on_proposal(proposal, context)

    assert vote.vote_choice == "REJECT"
    assert "COLD-CHAIN ARBITRAGE VETO" in vote.rationale
