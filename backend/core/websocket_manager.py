"""
Multi-Channel WebSocket Hub & Real-time Streaming Manager
Provides real-time pub/sub channels for Telemetry updates (/ws/telemetry)
and Multi-Agent Council reasoning traces (/ws/council).
"""
from typing import Dict, List, Any
from fastapi import WebSocket


class WebSocketHub:
    """
    Central Pub/Sub Hub managing multi-channel WebSocket connections:
    - 'telemetry': Stream live sensor and digital twin state updates.
    - 'council': Stream live reasoning traces, debate votes, and consensus verdicts.
    """
    def __init__(self):
        self._channels: Dict[str, List[WebSocket]] = {
            "telemetry": [],
            "council": []
        }

    async def connect(self, channel: str, websocket: WebSocket):
        """Accepts and subscribes a WebSocket to a designated channel."""
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = []
        self._channels[channel].append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        """Removes a disconnected WebSocket from its channel."""
        if channel in self._channels and websocket in self._channels[channel]:
            self._channels[channel].remove(websocket)

    def get_connection_count(self, channel: str) -> int:
        """Returns the number of active subscribers on a channel."""
        return len(self._channels.get(channel, []))

    async def broadcast(self, channel: str, message: Dict[str, Any]):
        """Broadcasts a JSON-serializable message payload to all subscribers on a channel."""
        connections = list(self._channels.get(channel, []))
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                self.disconnect(channel, conn)

    async def broadcast_council_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcasts a structured event to the '/ws/council' reasoning stream channel."""
        payload = {
            "channel": "council",
            "event": event_type,
            "data": data
        }
        await self.broadcast("council", payload)

    async def broadcast_telemetry(self, state: Dict[str, Any]):
        """Broadcasts digital twin telemetry update to '/ws/telemetry' subscribers."""
        payload = {
            "channel": "telemetry",
            "type": "TELEMETRY_UPDATE",
            "payload": state
        }
        await self.broadcast("telemetry", payload)


# Singleton WebSocket PubSub Hub instance
ws_hub = WebSocketHub()
