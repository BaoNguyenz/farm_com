"""
Unit test suite for AgronomistAgent autonomous rover weed management and chemical herbicide vetoes.
"""
import asyncio

import pytest

from backend.agents.agronomist import AgronomistAgent
from backend.core.farm_rover import RoverTask
from backend.core.rover_fleet import RoverFleetCoordinator
from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherSnapshot


@pytest.fixture
def weed_infested_farm() -> FarmDigitalTwin:
    zones = [
        PlotZone(
            id="Z_0_0",
            x=0,
            y=0,
            crop_type="Strawberries",
            growth_stage="vegetative",
            soil_moisture_pct=58.0,
            ndvi=0.48,  # Weed infestation gap
            health_status="weed_infested",
        ),
        PlotZone(
            id="Z_0_1",
            x=1,
            y=0,
            crop_type="Strawberries",
            growth_stage="flowering",
            soil_moisture_pct=62.0,
            ndvi=0.82,
            health_status="healthy",
        ),
    ]
    weather = WeatherSnapshot(
        temp_c=22.0,
        humidity_percent=65.0,
        wind_speed_ms=1.8,
        solar_radiation_mj=16.0,
        precipitation_mm=0.0,
    )
    return FarmDigitalTwin(
        farm_id="farm-weed-test",
        name="Test Rover Plot",
        latitude=11.94,
        longitude=108.45,
        zones=zones,
        current_weather=weather,
    )


def test_agronomist_weed_audit_and_dispatch(weed_infested_farm: FarmDigitalTwin) -> None:
    coordinator = RoverFleetCoordinator()
    agent = AgronomistAgent(rover_coordinator=coordinator)

    audit = agent.audit_weed_infestation_and_dispatch(weed_infested_farm)

    assert audit["infestation_plots_detected"] >= 1
    assert "Z_0_0" in audit["infestation_plot_ids"]
    assert audit["dispatched_missions_count"] >= 1

    mission = audit["missions"][0]
    assigned_rover_id = mission["assigned_rover_id"]
    rover = coordinator.rovers[assigned_rover_id]
    assert rover.state.task == RoverTask.WEEDING_PATROL


def test_agronomist_evaluate_includes_rover_management(weed_infested_farm: FarmDigitalTwin) -> None:
    agent = AgronomistAgent()
    opinion = asyncio.run(agent.evaluate(weed_infested_farm))

    assert "rover_weed_management" in opinion.data_points
    assert opinion.data_points["rover_weed_management"]["infestation_plots_detected"] >= 1


def test_agronomist_chemical_herbicide_veto() -> None:
    agent = AgronomistAgent()

    proposal = {
        "action_type": "apply_glyphosate_broad_spray",
        "action_domain": "agronomy",
        "urgency": "low",
    }
    context = {"plot_id": "Z_0_0"}

    vote = agent.vote_on_proposal(proposal, context)

    assert vote.vote_choice == "REJECT"
    assert "ORGANIC INTEGRITY VETO" in vote.rationale


def test_agronomist_mechanical_rover_endorsement() -> None:
    agent = AgronomistAgent()

    proposal = {
        "action_type": "dispatch_rover_mechanical_weeding",
        "action_domain": "robotics",
        "urgency": "medium",
    }
    context = {"plot_id": "Z_0_0"}

    vote = agent.vote_on_proposal(proposal, context)

    assert vote.vote_choice == "APPROVE"
    assert "zero-chemical autonomous mechanical weeding rover" in vote.rationale
