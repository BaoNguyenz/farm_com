"""
API v1 Router Definition
"""
from fastapi import APIRouter
from backend.api.v1.endpoints.farm import router as farm_router
from backend.api.v1.endpoints.simulation import router as simulation_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(farm_router)
api_v1_router.include_router(simulation_router)

__all__ = ["api_v1_router"]

