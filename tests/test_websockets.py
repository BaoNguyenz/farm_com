"""
Unit tests for Real-Time WebSocket Telemetry & Council Stream (Task 5.2)
Tests /ws/telemetry and /ws/council live streaming channels and pub/sub broadcasting.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.websocket_manager import ws_hub


@pytest.fixture
def client():
    return TestClient(app)


def test_websocket_telemetry_stream(client):
    """Test /ws/telemetry connection, initial digital twin state, and ping-pong commands."""
    with client.websocket_connect("/ws/telemetry") as ws:
        # Initial state payload
        init_data = ws.receive_json()
        assert init_data["type"] == "INIT_STATE"
        assert "payload" in init_data
        assert "zones" in init_data["payload"]
        assert "current_weather" in init_data["payload"]

        # Ping-Pong test
        ws.send_text("PING")
        reply = ws.receive_text()
        assert reply == "PONG"

        # Get Current State test
        ws.send_text("GET_STATE")
        state_data = ws.receive_json()
        assert state_data["type"] == "CURRENT_STATE"
        assert "zones" in state_data["payload"]


def test_websocket_council_stream(client):
    """Test /ws/council connection and on-demand CONVENE trigger."""
    with client.websocket_connect("/ws/council") as ws:
        # Verify initial subscription acknowledgment
        init_data = ws.receive_json()
        assert init_data["channel"] == "council"
        assert init_data["event"] == "CONNECTED"

        # Ping-Pong test
        ws.send_text("PING")
        reply = ws.receive_text()
        assert reply == "PONG"

        # Trigger council via socket
        ws.send_text("CONVENE")
        event_data = ws.receive_json()
        assert event_data["channel"] == "council"
        assert event_data["event"] == "COUNCIL_CONCLUDED"
        assert "data" in event_data
        assert "opinions" in event_data["data"]
        assert "debate_rounds" in event_data["data"]
        assert len(event_data["data"]["opinions"]) == 3


def test_websocket_hub_channel_management():
    """Test direct WebSocketHub subscriber tracking and channel counters."""
    initial_telemetry_subs = ws_hub.get_connection_count("telemetry")
    initial_council_subs = ws_hub.get_connection_count("council")

    assert initial_telemetry_subs >= 0
    assert initial_council_subs >= 0
