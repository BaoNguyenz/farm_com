"""
Integration tests for the Telemetry Export RESTful API Endpoints.
Verifies CSV and JSON serialization for zones, action history, and farm summary.
"""

import csv
import io
import pytest
from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_export_summary_endpoint(client):
    res = client.get("/api/v1/farm/export/summary")
    assert res.status_code == 200
    data = res.json()
    assert "farm_id" in data
    assert "total_zones" in data
    assert data["total_zones"] > 0
    assert "mean_soil_moisture_pct" in data
    assert "mean_ndvi" in data
    assert "crop_distribution" in data
    assert "health_distribution" in data


def test_export_zones_json(client):
    res = client.get("/api/v1/farm/export/zones?format=json")
    assert res.status_code == 200
    zones = res.json()
    assert isinstance(zones, list)
    assert len(zones) > 0
    first = zones[0]
    assert "id" in first
    assert "crop_type" in first
    assert "soil_moisture_pct" in first
    assert "ndvi" in first


def test_export_zones_csv(client):
    res = client.get("/api/v1/farm/export/zones?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment; filename=\"zones_telemetry.csv\"" in res.headers.get("content-disposition", "")

    csv_reader = csv.DictReader(io.StringIO(res.text))
    rows = list(csv_reader)
    assert len(rows) > 0
    assert "zone_id" in rows[0]
    assert "crop_type" in rows[0]
    assert "accumulated_gdd" in rows[0]
    assert "ndvi" in rows[0]
    assert "soil_moisture_pct" in rows[0]


def test_export_actions_json_and_csv(client):
    # JSON export
    res_json = client.get("/api/v1/farm/export/actions?format=json")
    assert res_json.status_code == 200
    assert isinstance(res_json.json(), list)

    # CSV export
    res_csv = client.get("/api/v1/farm/export/actions?format=csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]

    csv_reader = csv.DictReader(io.StringIO(res_csv.text))
    fieldnames = csv_reader.fieldnames or []
    assert "agent_name" in fieldnames
    assert "action_type" in fieldnames
    assert "rationale" in fieldnames


def test_export_full_snapshot(client):
    res = client.get("/api/v1/farm/export/full")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    snapshot = res.json()
    assert "farm_id" in snapshot
    assert "zones" in snapshot
    assert "current_weather" in snapshot
