"""
Integration test suite for Greenhouse CEA and Bio-Acoustic Pollination REST API endpoints.
"""
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_greenhouse_telemetry() -> None:
    res = client.get("/api/v1/greenhouse/telemetry?ambient_temp_c=25.0&ambient_humidity_pct=65.0&solar_radiation_mj=18.0")
    assert res.status_code == 200
    data = res.json()
    assert data["greenhouse_id"] == "GH-POLYHOUSE-01"
    assert "air_temp_c" in data
    assert "vpd_kpa" in data
    assert "canopy_net_photosynthesis_umol_m2_s" in data
    assert "actuators" in data
    assert "roof_vent_pct" in data["actuators"]


def test_adjust_greenhouse_vents_and_interlock() -> None:
    payload = {
        "roof_vent_pct": 70.0,
        "side_curtain_pct": 50.0,
        "pad_and_fan_active": True,
        "shade_screen_deployed": False,
    }
    res = client.post("/api/v1/greenhouse/adjust-vents", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["actuators"]["roof_vent_pct"] == 70.0
    assert data["actuators"]["pad_and_fan_active"] is True
    # CO2 dosing valve must be shut off when roof vents >= 55%
    assert data["actuators"]["co2_dosing_valve_open"] is False


def test_inject_co2_anti_exhaust_interlock() -> None:
    # 1. Reject injection when vents are currently wide open (70%)
    res_rejected = client.post(
        "/api/v1/greenhouse/inject-co2",
        json={"target_co2_ppm": 900.0, "dosing_rate_kg_h": 4.5, "force_override": False},
    )
    assert res_rejected.status_code == 400
    assert "ANTI-EXHAUST INTERLOCK" in res_rejected.json()["detail"]

    # 2. Restrict vents to 20%
    client.post(
        "/api/v1/greenhouse/adjust-vents",
        json={"roof_vent_pct": 20.0, "side_curtain_pct": 15.0, "pad_and_fan_active": False, "shade_screen_deployed": False},
    )

    # 3. Successful injection when vents are restricted
    res_success = client.post(
        "/api/v1/greenhouse/inject-co2",
        json={"target_co2_ppm": 950.0, "dosing_rate_kg_h": 5.0, "force_override": False},
    )
    assert res_success.status_code == 200
    data = res_success.json()
    assert data["actuators"]["co2_dosing_valve_open"] is True
    assert data["co2_concentration_ppm"] == 950.0


def test_photosynthesis_curve() -> None:
    res = client.get("/api/v1/greenhouse/photosynthesis-curve?co2_ppm=850.0&temp_c=24.0")
    assert res.status_code == 200
    curve = res.json()
    assert len(curve) == 10
    assert curve[0]["par_umol_m2_s"] == 0
    assert curve[-1]["par_umol_m2_s"] == 1500
    assert curve[-1]["pn_umol_m2_s"] > curve[1]["pn_umol_m2_s"]


def test_pollination_status() -> None:
    res = client.get("/api/v1/pollination/status")
    assert res.status_code == 200
    data = res.json()
    assert "average_visitations_per_flower" in data
    assert "zone_audits" in data
    assert len(data["zone_audits"]) >= 2


def test_pollination_zone_audit() -> None:
    # Optimal condition
    res_optimal = client.get(
        "/api/v1/pollination/zone/ZONE_GH_1?flower_count_per_m2=40&buzz_events_per_hour=120&ambient_temp_c=23.0"
    )
    assert res_optimal.status_code == 200
    opt_data = res_optimal.json()
    assert opt_data["visitations_per_flower"] == 3.0
    assert opt_data["pollination_status"] == "optimal"
    assert opt_data["fruit_deformation_risk_pct"] <= 5.0

    # Thermal cessation condition (>32°C)
    res_heat = client.get(
        "/api/v1/pollination/zone/ZONE_GH_1?flower_count_per_m2=40&buzz_events_per_hour=120&ambient_temp_c=36.0"
    )
    assert res_heat.status_code == 200
    heat_data = res_heat.json()
    assert heat_data["foraging_thermal_stress"] is True
    assert heat_data["buzz_events_count_per_hour"] == 0
    assert "THERMAL FORAGING CESSATION" in heat_data["recommended_action"]


def test_simulate_acoustic_buzz() -> None:
    # Floral buzz sonication detection (~345 Hz)
    res_sonication = client.post(
        "/api/v1/pollination/simulate-buzz",
        json={"frequency_hz": 345.0, "duration_seconds": 1.5, "amplitude_db": -16.0, "zone_id": "ZONE_GH_1"},
    )
    assert res_sonication.status_code == 200
    son_data = res_sonication.json()
    assert son_data["is_valid_floral_sonication"] is True
    assert son_data["classification"] == "bombus_floral_sonication"

    # Flight wingbeat detection (~180 Hz)
    res_flight = client.post(
        "/api/v1/pollination/simulate-buzz",
        json={"frequency_hz": 180.0, "duration_seconds": 1.2, "amplitude_db": -22.0, "zone_id": "ZONE_GH_1"},
    )
    assert res_flight.status_code == 200
    flight_data = res_flight.json()
    assert flight_data["is_valid_floral_sonication"] is False
    assert flight_data["classification"] == "flight_wingbeat"
