"""
Unit test suite for CEA Greenhouse and Bio-Acoustic Pollination agent intelligence.
Tests AgronomistAgent and MarketAgent microclimate and pollination decision-making.
"""
import pytest

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherTelemetry


@pytest.fixture
def mock_flowering_farm() -> FarmDigitalTwin:
    """Creates a digital twin with blooming strawberries under mild weather."""
    weather = WeatherTelemetry(
        temp_c=23.5,
        humidity_percent=68.0,
        solar_radiation_mj=18.5,
        wind_speed_mps=1.8,
        rain_probability=0.0,
    )
    zones = [
        PlotZone(
            id="ZONE_GH_1",
            x=0,
            y=0,
            crop_type="Strawberries",
            growth_stage="flowering",
            soil_moisture_pct=60.0,
            soil_temp_c=20.0,
            soil_ph=6.2,
            ndvi=0.82,
            ndwi=0.35,
            health_status="optimal",
            accumulated_gdd=350.0,
        ),
        PlotZone(
            id="ZONE_GH_2",
            x=1,
            y=0,
            crop_type="Strawberries",
            growth_stage="fruiting",
            soil_moisture_pct=58.0,
            soil_temp_c=20.5,
            soil_ph=6.3,
            ndvi=0.79,
            ndwi=0.32,
            health_status="optimal",
            accumulated_gdd=380.0,
        ),
    ]
    return FarmDigitalTwin(farm_id="FARM_CEA_TEST", zones=zones, current_weather=weather)


@pytest.mark.anyio
async def test_agronomist_pollination_and_cea_evaluation(mock_flowering_farm: FarmDigitalTwin) -> None:
    agronomist = AgronomistAgent()
    opinion = await agronomist.evaluate(mock_flowering_farm)

    assert opinion.agent_id == "agent_agronomist"
    assert "greenhouse_cea" in opinion.data_points
    assert "pollination_report" in opinion.data_points

    cea = opinion.data_points["greenhouse_cea"]
    assert "air_temp_c" in cea
    assert "vpd_kpa" in cea
    assert "canopy_net_photosynthesis_umol_m2_s" in cea

    pollination = opinion.data_points["pollination_report"]
    assert "average_visitations_per_flower" in pollination
    assert "zone_audits" in pollination


def test_agronomist_co2_vent_interlock_votes() -> None:
    agronomist = AgronomistAgent()

    # Veto CO2 dosing when vents are wide open
    veto_vote = agronomist.vote_on_proposal(
        proposal={"action_type": "co2_injection_dosing", "action_domain": "cea_climate"},
        context={"roof_vent_pct": 75.0},
    )
    assert veto_vote.vote_choice == "REJECT"
    assert "CO2 LOSS VETO" in veto_vote.rationale

    # Veto opening vents when CO2 enrichment is actively running
    vent_veto = agronomist.vote_on_proposal(
        proposal={"action_type": "open_vent_ridge_motor", "action_domain": "cea_climate"},
        context={"co2_dosing_active": True},
    )
    assert vent_veto.vote_choice == "REJECT"
    assert "VENT VETO" in vent_veto.rationale

    # Endorse supplemental bumblebee hive placement
    hive_vote = agronomist.vote_on_proposal(
        proposal={"action_type": "deploy_supplementary_bombus_hive", "action_domain": "pollination"},
        context={},
    )
    assert hive_vote.vote_choice == "APPROVE"
    assert "bumblebee" in hive_vote.rationale.lower()


def test_market_co2_enrichment_economics() -> None:
    market = MarketAgent()

    # Highly profitable scenario: 10 kg CO2 dosed, 15% yield gain on high-value strawberries
    econ_profit = market.evaluate_co2_enrichment_economics(
        co2_kg_dosed=10.0,
        projected_yield_gain_pct=15.0,
        crop_type="Strawberries",
        area_m2=200.0,
    )
    assert econ_profit["is_profitable"] is True
    assert econ_profit["roi_ratio"] > 1.0
    assert econ_profit["net_profit_vnd"] > 0

    # Unprofitable scenario: 25 kg CO2 dosed, 2% yield gain on low-value Bell Pepper
    econ_loss = market.evaluate_co2_enrichment_economics(
        co2_kg_dosed=25.0,
        projected_yield_gain_pct=2.0,
        crop_type="Bell Pepper",
        area_m2=50.0,
    )
    assert econ_loss["is_profitable"] is False
    assert econ_loss["roi_ratio"] < 1.0
    assert econ_loss["net_profit_vnd"] < 0


def test_market_co2_enrichment_voting() -> None:
    market = MarketAgent()

    # Reject CO2 dosing if roof vents are open >50%
    vote_vent_open = market.vote_on_proposal(
        proposal={"action_type": "co2_enrichment_pulse"},
        context={"roof_vent_pct": 65.0, "projected_roi": 3.0, "is_profitable": True},
    )
    assert vote_vent_open.vote_choice == "REJECT"
    assert "CO2 ECONOMIC VETO" in vote_vent_open.rationale

    # Reject CO2 dosing if unprofitable ROI
    vote_loss = market.vote_on_proposal(
        proposal={"action_type": "co2_dosing_rate"},
        context={"roof_vent_pct": 20.0, "projected_roi": 0.45, "is_profitable": False},
    )
    assert vote_loss.vote_choice == "REJECT"

    # Approve CO2 dosing when vents are closed and ROI is favorable
    vote_approve = market.vote_on_proposal(
        proposal={"action_type": "co2_enrichment_injection"},
        context={"roof_vent_pct": 15.0, "projected_roi": 2.8, "is_profitable": True},
    )
    assert vote_approve.vote_choice == "APPROVE"
    assert "yield uplift" in vote_approve.rationale
