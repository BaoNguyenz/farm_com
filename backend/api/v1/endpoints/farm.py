"""
Farm Digital Twin REST API Endpoints (v1)
Provides spatial grid state, individual zone diagnostics, and filtered telemetry queries.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Response
from typing import Dict, Any, List, Optional
from backend.core.twin_state import FarmDigitalTwin
from backend.core.telemetry_export import TelemetryExporter


router = APIRouter(prefix="/farm", tags=["Farm Digital Twin v1"])


def get_farm_state() -> FarmDigitalTwin:
    """Dependency injecting singleton farm digital twin instance."""
    from backend.main import farm_instance
    return farm_instance


@router.get("/state")
async def get_state(
    include_history: bool = Query(True, description="Whether to include historical action logs"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Retrieve complete Digital Twin state representation including weather and zones."""
    data = farm.model_dump()
    if not include_history:
        data.pop("action_history", None)
    return data


@router.get("/dimensions")
async def get_dimensions(farm: FarmDigitalTwin = Depends(get_farm_state)) -> Dict[str, Any]:
    """Retrieve spatial grid dimensions and total land area."""
    total_zones = len(farm.zones)
    # Each zone benchmark is 25 m2 (5m x 5m)
    area_m2 = total_zones * 25.0
    return {
        "farm_id": farm.farm_id,
        "name": farm.name,
        "grid_width": farm.grid_width,
        "grid_height": farm.grid_height,
        "total_zones": total_zones,
        "total_area_m2": area_m2,
        "plot_size_m2": 25.0,
        "coordinates": {
            "latitude": farm.latitude,
            "longitude": farm.longitude
        }
    }


@router.get("/zones")
async def list_zones(
    status: Optional[str] = Query(None, description="Filter by health status (e.g. healthy, water_stressed)"),
    crop: Optional[str] = Query(None, description="Filter by crop type name"),
    min_moisture: Optional[float] = Query(None, description="Minimum soil moisture percentage"),
    max_moisture: Optional[float] = Query(None, description="Maximum soil moisture percentage"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> List[Dict[str, Any]]:
    """Query plot zones with optional attribute and threshold filters."""
    results: List[Dict[str, Any]] = []

    for zone in farm.zones:
        if status and zone.health_status.lower() != status.lower():
            continue
        if crop and crop.lower() not in zone.crop_type.lower():
            continue
        if min_moisture is not None and zone.soil_moisture_pct < min_moisture:
            continue
        if max_moisture is not None and zone.soil_moisture_pct > max_moisture:
            continue
        results.append(zone.model_dump())

    return results


@router.get("/zones/{zone_id}")
async def get_zone_detail(
    zone_id: str,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Retrieve fine-grained biophysical diagnostics and spatial neighbors for a zone."""
    zone = farm.get_zone(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail=f"Zone '{zone_id}' not found.")

    # Calculate adjacent neighbors on grid
    neighbors_von_neumann: List[str] = []
    neighbors_moore: List[str] = []

    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nx, ny = zone.x + dx, zone.y + dy
        if 0 <= nx < farm.grid_width and 0 <= ny < farm.grid_height:
            neighbors_von_neumann.append(f"Z_{nx}_{ny}")

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = zone.x + dx, zone.y + dy
            if 0 <= nx < farm.grid_width and 0 <= ny < farm.grid_height:
                neighbors_moore.append(f"Z_{nx}_{ny}")

    data = zone.model_dump()
    data["spatial_topology"] = {
        "von_neumann_neighbors": neighbors_von_neumann,
        "moore_neighbors": neighbors_moore
    }
    return data


@router.get("/export/summary")
async def export_farm_summary(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Retrieve statistical telemetry aggregates across all plot zones."""
    return TelemetryExporter.export_summary_dict(farm)


@router.get("/export/zones")
async def export_zones(
    format: str = Query("json", pattern="^(json|csv)$", description="Format to export: 'json' or 'csv'"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Any:
    """Export current zone biophysical telemetry in CSV or JSON format."""
    if format == "csv":
        csv_data = TelemetryExporter.export_zones_csv(farm)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="zones_telemetry.csv"'}
        )
    return [z.model_dump() for z in farm.zones]


@router.get("/export/actions")
async def export_actions(
    format: str = Query("json", pattern="^(json|csv)$", description="Format to export: 'json' or 'csv'"),
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Any:
    """Export historical council action logs in CSV or JSON format."""
    if format == "csv":
        csv_data = TelemetryExporter.export_actions_csv(farm)
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="action_history.csv"'}
        )
    return [a.model_dump() for a in farm.action_history]


@router.get("/export/full")
async def export_full_farm(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Response:
    """Export complete digital twin snapshot as a formatted JSON document."""
    raw_json = TelemetryExporter.export_farm_json(farm)
    return Response(
        content=raw_json,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{farm.farm_id}_snapshot.json"'}
    )
