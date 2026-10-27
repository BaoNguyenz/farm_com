"""
Farm_com - Autonomous Farm OS Entrypoint
FastAPI Application, WebSocket Server & Digital Twin Controller
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from backend.config import settings
from backend.core.twin_state import create_default_farm
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


# WebSocket Connection Manager for Live Telemetry
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

ws_manager = ConnectionManager()

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send immediate initial state
        await websocket.send_json({"type": "INIT_STATE", "payload": farm_instance.model_dump()})
        while True:
            data = await websocket.receive_text()
            # Echo or process incoming socket commands
            if data == "PING":
                await websocket.send_text("PONG")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# Mount Static UI Directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
