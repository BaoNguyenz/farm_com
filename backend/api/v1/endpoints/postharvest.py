"""
Post-Harvest Produce Respiration & Modified Atmosphere Packaging (MAP) REST API Endpoints (v1).
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.postharvest_map import (
    ColdChainAuditLog,
    MAPPackageDesignResult,
    ModifiedAtmospherePackagingEngine,
    PackagingFilmType,
)
from backend.core.postharvest_respiration import (
    PerishableCommodity,
    PostHarvestRespirationEngine,
    RespirationKineticsResult,
)

router = APIRouter(prefix="/postharvest", tags=["Post-Harvest MAP & Respiration"])

_respiration_engine = PostHarvestRespirationEngine(PerishableCommodity.STRAWBERRIES)
_map_engine = ModifiedAtmospherePackagingEngine(PackagingFilmType.MICRO_PERFORATED_PP)


class RespirationEvalRequest(BaseModel):
    commodity: PerishableCommodity = PerishableCommodity.STRAWBERRIES
    storage_temp_c: float = Field(2.0, ge=-2.0, le=35.0)
    ambient_rh_pct: float = Field(90.0, ge=30.0, le=100.0)
    o2_pct: float = Field(20.9, ge=0.1, le=25.0)
    co2_pct: float = Field(0.04, ge=0.0, le=30.0)
    elapsed_days_in_store: float = Field(1.0, ge=0.0, le=60.0)


class MAPDesignRequest(BaseModel):
    film_type: PackagingFilmType = PackagingFilmType.MICRO_PERFORATED_PP
    fruit_mass_kg: float = Field(0.5, ge=0.1, le=10.0)
    package_area_m2: float = Field(0.04, ge=0.005, le=1.0)
    storage_temp_c: float = Field(2.0, ge=-2.0, le=25.0)
    fruit_r_o2_ml_kg_h: float = Field(8.5, ge=1.0, le=100.0)


class ColdChainAuditRequest(BaseModel):
    lot_id: str = Field(..., min_length=3, max_length=50)
    hourly_temperatures_c: list[float] = Field(..., min_length=1)
    base_temp_c: float = Field(3.0, ge=0.0, le=10.0)
    max_allowable_degree_hours: float = Field(45.0, ge=10.0, le=200.0)


@router.get("/telemetry")
async def get_postharvest_telemetry() -> dict[str, Any]:
    """Retrieves operational telemetry for post-harvest berry preservation and MAP status."""
    resp_res = _respiration_engine.evaluate_respiration(
        storage_temp_c=2.0,
        ambient_rh_pct=92.0,
        o2_pct=4.5,
        co2_pct=12.5,
    )
    map_res = _map_engine.solve_equilibrium_atmosphere(
        fruit_mass_kg=0.5,
        package_area_m2=0.04,
        storage_temp_c=2.0,
        fruit_r_o2_ml_kg_h=resp_res.r_o2_ml_kg_h,
    )
    return {
        "status": "operational",
        "commodity": _respiration_engine.commodity.value,
        "cold_room": {
            "storage_temp_c": resp_res.storage_temp_c,
            "ambient_rh_pct": resp_res.ambient_rh_pct,
            "r_o2_ml_kg_h": resp_res.r_o2_ml_kg_h,
            "respiratory_quotient": resp_res.respiratory_quotient,
            "hourly_weight_loss_pct": resp_res.hourly_weight_loss_pct,
            "remaining_shelf_life_days": resp_res.remaining_shelf_life_days,
            "freshness_index_score": resp_res.freshness_index_score,
            "anaerobic_risk": resp_res.anaerobic_fermentation_risk,
        },
        "map_packaging": {
            "film_type": map_res.film_type.value,
            "equilibrium_o2_pct": map_res.equilibrium_o2_pct,
            "equilibrium_co2_pct": map_res.equilibrium_co2_pct,
            "botrytis_inhibition_pct": map_res.botrytis_inhibition_pct,
            "package_status": map_res.package_status,
        },
    }


@router.post("/evaluate-respiration", response_model=RespirationKineticsResult)
async def evaluate_produce_respiration(req: RespirationEvalRequest) -> RespirationKineticsResult:
    """Calculates Michaelis-Menten fruit respiration, weight loss, and shelf life."""
    engine = PostHarvestRespirationEngine(req.commodity)
    return engine.evaluate_respiration(
        storage_temp_c=req.storage_temp_c,
        ambient_rh_pct=req.ambient_rh_pct,
        o2_pct=req.o2_pct,
        co2_pct=req.co2_pct,
        elapsed_days_in_store=req.elapsed_days_in_store,
    )


@router.post("/design-map-package", response_model=MAPPackageDesignResult)
async def design_map_package(req: MAPDesignRequest) -> MAPPackageDesignResult:
    """Solves steady-state equilibrium modified atmosphere and fungal mold suppression."""
    engine = ModifiedAtmospherePackagingEngine(req.film_type)
    return engine.solve_equilibrium_atmosphere(
        fruit_mass_kg=req.fruit_mass_kg,
        package_area_m2=req.package_area_m2,
        storage_temp_c=req.storage_temp_c,
        fruit_r_o2_ml_kg_h=req.fruit_r_o2_ml_kg_h,
    )


@router.post("/audit-cold-chain", response_model=ColdChainAuditLog)
async def audit_cold_chain(req: ColdChainAuditRequest) -> ColdChainAuditLog:
    """Audits reefer transit temperature logger and assigns export quality grade."""
    return _map_engine.audit_cold_chain_transit(
        lot_id=req.lot_id,
        hourly_temperatures_c=req.hourly_temperatures_c,
        base_temp_c=req.base_temp_c,
        max_allowable_degree_hours=req.max_allowable_degree_hours,
    )
