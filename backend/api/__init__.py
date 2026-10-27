"""
FastAPI Route Controllers Package
Exports v1 versioned API routers and legacy routers.
"""
from backend.api.routes_farm import router as legacy_farm_router
from backend.api.routes_agents import router as legacy_agent_router
from backend.api.v1 import api_v1_router

__all__ = [
    "legacy_farm_router",
    "legacy_agent_router",
    "api_v1_router"
]
