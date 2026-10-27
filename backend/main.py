"""
Farm_com - Autonomous Farm OS Entrypoint
FastAPI Application, WebSocket Server & Digital Twin Controller
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.core.twin_state import create_default_farm
from backend.core.websocket_manager import ws_hub
from backend.ingestion.weather_client import WeatherClient
from backend.ingestion.satellite_client import SatelliteClient
from backend.ingestion.sensor_sim import SensorSimulator
from backend.agents.agronomist import AgronomistAgent
from backend.agents.irrigation import IrrigationAgent
from backend.agents.market import MarketAgent
from backend.agents.commander import CommanderAgent
from backend.api.routes_farm import router as farm_router
from backend.api.routes_agents import router as agent_router
from backend.api.v1 import api_v1_router



# 1. Instantiate Core Farm Digital Twin State
farm_instance = create_default_farm(width=settings.grid_size_x, height=settings.grid_size_y)

# 2. Instantiate Telemetry & Ingestion Clients
weather_client = WeatherClient(lat=settings.farm_lat, lon=settings.farm_lon)
satellite_client = SatelliteClient(client_id=settings.copernicus_client_id, client_secret=settings.copernicus_client_secret)
sensor_sim = SensorSimulator(farm=farm_instance)

# 3. Instantiate Agent Swarm
agronomist_agent = AgronomistAgent()
irrigation_agent = IrrigationAgent()
market_agent = MarketAgent()
commander_agent = CommanderAgent(
    agronomist=agronomist_agent,
    irrigation=irrigation_agent,
    market=market_agent
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Fetch initial real weather conditions
    try:
        farm_instance.current_weather = await weather_client.fetch_current_weather()
    except Exception:
        pass
    yield
    # Shutdown logic if any

app = FastAPI(
    title="Farm_com: Autonomous Farm OS",
    description="Digital Twin and Multi-Agent Swarm for Precision Agriculture",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(api_v1_router)
app.include_router(farm_router)
app.include_router(agent_router)

# Backward-compatible alias for existing imports
ws_manager = ws_hub



@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """Real-time streaming channel for Digital Twin telemetry, sensor state, and weather."""
    await ws_hub.connect("telemetry", websocket)
    try:
        await websocket.send_json({"type": "INIT_STATE", "payload": farm_instance.model_dump()})
        while True:
            data = await websocket.receive_text()
            if data == "PING":
                await websocket.send_text("PONG")
            elif data == "GET_STATE":
                await websocket.send_json({"type": "CURRENT_STATE", "payload": farm_instance.model_dump()})
    except WebSocketDisconnect:
        ws_hub.disconnect("telemetry", websocket)


@app.websocket("/ws/council")
async def websocket_council(websocket: WebSocket):
    """Real-time streaming channel for Multi-Agent Council deliberations, debates, and verdicts."""
    await ws_hub.connect("council", websocket)
    try:
        await websocket.send_json({
            "channel": "council",
            "event": "CONNECTED",
            "message": "Subscribed to Multi-Agent Council reasoning trace stream."
        })
        while True:
            data = await websocket.receive_text()
            if data == "PING":
                await websocket.send_text("PONG")
            elif "CONVENE" in data:
                from backend.api.v1.endpoints.audit import _global_dispatcher
                verdict = await commander_agent.convene_council(farm_instance, dispatcher=_global_dispatcher)
                await ws_hub.broadcast_council_event("COUNCIL_CONCLUDED", verdict.to_dict())
    except WebSocketDisconnect:
        ws_hub.disconnect("council", websocket)


# Mount Static UI Directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
