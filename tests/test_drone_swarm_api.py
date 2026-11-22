"""
Integration test suite for Autonomous UAV Swarm REST API and Agent Council Debate.
"""

from fastapi.testclient import TestClient

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.main import app

client = TestClient(app)


def test_get_drone_swarm_telemetry():
    """Verify GET /api/v1/drone-swarm/telemetry returns fleet state and safety audit."""
    response = client.get("/api/v1/drone-swarm/telemetry")
    assert response.status_code == 200
    data = response.json()

    assert data["fleet_size"] == 2
    assert data["fleet_status"] == "AIRBORNE_COOPERATIVE"
    assert len(data["drones"]) == 2
    assert data["drones"][0]["drone_id"] == "UAV-Alpha"
    assert "weather_safety_audit" in data
    assert data["weather_safety_audit"]["is_flight_permitted"] is True
    assert "economic_roi" in data
    assert data["economic_roi"]["is_highly_profitable"] is True


def test_post_plan_swarm_mission_success():
    """Verify POST /api/v1/drone-swarm/plan-mission computes Boustrophedon Voronoi plan."""
    payload = {
        "farm_width_m": 250.0,
        "farm_height_m": 120.0,
        "altitude_m": 35.0,
        "fleet_size": 3,
        "wind_speed_m_s": 4.0,
        "wind_direction_deg": 90.0,
    }
    response = client.post("/api/v1/drone-swarm/plan-mission", json=payload)
    assert response.status_code == 200
    plan = response.json()

    assert "SWARM-MSN-35M-3UAV" in plan["mission_id"]
    assert plan["total_area_ha"] == 3.0
    assert len(plan["partitions"]) == 3
    assert "UAV-A" in plan["partitions"]
    assert "UAV-B" in plan["partitions"]
    assert "UAV-C" in plan["partitions"]
    assert plan["fleet_total_distance_m"] > 0
    assert plan["gsd_cm_per_px"] > 0


def test_post_plan_swarm_mission_high_wind_rejected():
    """Verify mission generation is rejected when wind speed exceeds safety envelope (12 m/s)."""
    payload = {
        "farm_width_m": 200.0,
        "farm_height_m": 100.0,
        "altitude_m": 35.0,
        "fleet_size": 2,
        "wind_speed_m_s": 14.5,  # unsafe wind
        "wind_direction_deg": 45.0,
    }
    response = client.post("/api/v1/drone-swarm/plan-mission", json=payload)
    assert response.status_code == 400
    assert "exceeds max safe flight envelope" in response.json()["detail"]


def test_post_check_collision_cone():
    """Verify POST /api/v1/drone-swarm/check-collision evaluates RVO risk."""
    payload = {
        "drone_a": {
            "drone_id": "UAV-Alpha",
            "position": {"x": 10.0, "y": 50.0},
            "altitude_m": 35.0,
            "vx_m_s": 8.0,
            "vy_m_s": 0.0,
            "vz_m_s": 0.0,
            "battery_soc_pct": 80.0,
            "battery_capacity_wh": 160.0,
        },
        "drone_b": {
            "drone_id": "UAV-Beta",
            "position": {"x": 30.0, "y": 50.0},
            "altitude_m": 35.0,
            "vx_m_s": -8.0,
            "vy_m_s": 0.0,
            "vz_m_s": 0.0,
            "battery_soc_pct": 85.0,
            "battery_capacity_wh": 160.0,
        },
    }
    response = client.post("/api/v1/drone-swarm/check-collision", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["collision_imminent"] is True
    assert res["recommended_action"] == "altitude_separation"


def test_post_evaluate_rth():
    """Verify POST /api/v1/drone-swarm/evaluate-rth calculates aerodynamic power and reserve."""
    payload = {
        "drone": {
            "drone_id": "UAV-Alpha",
            "position": {"x": 150.0, "y": 200.0},
            "altitude_m": 35.0,
            "vx_m_s": 0.0,
            "vy_m_s": 0.0,
            "vz_m_s": 0.0,
            "battery_soc_pct": 8.0,
            "battery_capacity_wh": 160.0,
            "base_station": {"x": 0.0, "y": 0.0},
        },
        "wind_speed_m_s": 5.0,
        "wind_direction_deg": 180.0,
    }
    response = client.post("/api/v1/drone-swarm/evaluate-rth", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["rth_alert"] is True
    assert res["distance_to_home_m"] > 200.0
    assert res["power_draw_w"] > 50.0


def test_post_handoff_mission():
    """Verify POST /api/v1/drone-swarm/handoff-mission transfers waypoints."""
    payload = {
        "exhausted_drone": {
            "drone_id": "UAV-Alpha",
            "position": {"x": 50.0, "y": 50.0},
            "battery_soc_pct": 14.0,
            "remaining_waypoints": [
                {
                    "index": 1,
                    "x": 80.0,
                    "y": 50.0,
                    "z_agl": 35.0,
                    "action": "sweep_pass",
                    "speed_m_s": 8.0,
                    "trigger_camera": True,
                    "drone_id": "UAV-Alpha",
                }
            ],
        },
        "receiving_drone": {
            "drone_id": "UAV-Beta",
            "position": {"x": 55.0, "y": 50.0},
            "battery_soc_pct": 82.0,
            "remaining_waypoints": [],
        },
    }
    response = client.post("/api/v1/drone-swarm/handoff-mission", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["handoff_successful"] is True
    assert res["transferred_waypoint_count"] == 1


def test_agent_council_debate_on_uav_launch():
    """Verify Agronomist and Market agent votes on UAV swarm mission proposals."""
    agronomist = AgronomistAgent()
    market = MarketAgent()

    # Nominal weather: both approve
    nominal_context = {"wind_speed_m_s": 4.5, "rain_rate_mm_h": 0.0}
    proposal = {"action_type": "launch_drone_swarm", "action_domain": "scouting"}

    agro_vote = agronomist.vote_on_proposal(proposal=proposal, context=nominal_context)
    market_vote = market.vote_on_proposal(proposal=proposal, context=nominal_context)

    assert agro_vote.vote.lower() in ("approve", "accept")
    assert market_vote.vote.lower() in ("approve", "accept")

    # High wind condition: Agronomist issues safety veto
    storm_context = {"wind_speed_m_s": 14.0, "rain_rate_mm_h": 2.0}
    veto_vote = agronomist.vote_on_proposal(proposal=proposal, context=storm_context)

    assert veto_vote.vote.lower() in ("reject", "veto")
    assert "HIGH WIND GUST VETO" in veto_vote.rationale
