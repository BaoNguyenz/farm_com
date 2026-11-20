"""
API v1 Router Definition
"""
from fastapi import APIRouter

from backend.api.v1.endpoints.agrivoltaics import router as agrivoltaics_router
from backend.api.v1.endpoints.aquaponics import router as aquaponics_router
from backend.api.v1.endpoints.audit import router as audit_router
from backend.api.v1.endpoints.biocontrol import router as biocontrol_router
from backend.api.v1.endpoints.carbon import router as carbon_router
from backend.api.v1.endpoints.cold_chain import router as cold_chain_router
from backend.api.v1.endpoints.council import router as council_router
from backend.api.v1.endpoints.drone import router as drone_router
from backend.api.v1.endpoints.epidemiology import router as epidemiology_router
from backend.api.v1.endpoints.farm import router as farm_router
from backend.api.v1.endpoints.fertigation import router as fertigation_router
from backend.api.v1.endpoints.greenhouse import router as greenhouse_router
from backend.api.v1.endpoints.iot import router as iot_router
from backend.api.v1.endpoints.microgrid import router as microgrid_router
from backend.api.v1.endpoints.pollination import router as pollination_router
from backend.api.v1.endpoints.rovers import router as rovers_router
from backend.api.v1.endpoints.scenarios import router as scenarios_router
from backend.api.v1.endpoints.simulation import router as simulation_router
from backend.api.v1.endpoints.soil_microbiome import router as soil_microbiome_router
from backend.api.v1.endpoints.subsurface_fertigation import (
    router as subsurface_fertigation_router,
)
from backend.api.v1.endpoints.traceability import router as traceability_router
from backend.api.v1.endpoints.water_resilience import router as water_resilience_router
from backend.api.v1.endpoints.yield_forecast import router as yield_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(farm_router)
api_v1_router.include_router(simulation_router)
api_v1_router.include_router(council_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(scenarios_router)
api_v1_router.include_router(iot_router)
api_v1_router.include_router(fertigation_router)
api_v1_router.include_router(carbon_router)
api_v1_router.include_router(epidemiology_router)
api_v1_router.include_router(microgrid_router)
api_v1_router.include_router(drone_router)
api_v1_router.include_router(yield_router)
api_v1_router.include_router(traceability_router)
api_v1_router.include_router(soil_microbiome_router)
api_v1_router.include_router(cold_chain_router)
api_v1_router.include_router(rovers_router)
api_v1_router.include_router(greenhouse_router)
api_v1_router.include_router(pollination_router)
api_v1_router.include_router(water_resilience_router)
api_v1_router.include_router(biocontrol_router)
api_v1_router.include_router(aquaponics_router)
api_v1_router.include_router(agrivoltaics_router)
api_v1_router.include_router(subsurface_fertigation_router)

__all__ = ["api_v1_router"]



