"""
Telemetry Exporter for Farm Digital Twin.

Serializes agronomic state, spatial plot telemetry, environmental sensors,
and council operational history into standardized JSON and CSV formats.
"""

from typing import Dict, Any
import csv
import io
import json

from backend.core.twin_state import FarmDigitalTwin


class TelemetryExporter:
    """
    Utility class to serialize digital twin state and telemetry time-series
    for analytical consumption, reporting, and archival.
    """

    @staticmethod
    def export_farm_json(farm: FarmDigitalTwin, indent: int = 2) -> str:
        """
        Serializes the complete digital twin state into a JSON string.
        """
        data = farm.model_dump()
        return json.dumps(data, indent=indent, default=str)

    @staticmethod
    def export_zones_csv(farm: FarmDigitalTwin) -> str:
        """
        Exports all current plot zone metrics to standard CSV format.
        """
        output = io.StringIO()
        fieldnames = [
            "zone_id",
            "x",
            "y",
            "crop_type",
            "growth_stage",
            "accumulated_gdd",
            "soil_moisture_pct",
            "soil_ph",
            "soil_temp_c",
            "ndvi",
            "ndwi",
            "health_status",
            "last_irrigated_timestamp",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for z in farm.zones:
            writer.writerow({
                "zone_id": z.id,
                "x": z.x,
                "y": z.y,
                "crop_type": z.crop_type,
                "growth_stage": z.growth_stage,
                "accumulated_gdd": round(z.accumulated_gdd, 2),
                "soil_moisture_pct": round(z.soil_moisture_pct, 2),
                "soil_ph": round(z.soil_ph, 2),
                "soil_temp_c": round(z.soil_temp_c, 2),
                "ndvi": round(z.ndvi, 4),
                "ndwi": round(z.ndwi, 4),
                "health_status": z.health_status,
                "last_irrigated_timestamp": z.last_irrigated_timestamp,
            })

        return output.getvalue()

    @staticmethod
    def export_actions_csv(farm: FarmDigitalTwin) -> str:
        """
        Exports the autonomous multi-agent council action history to CSV format.
        """
        output = io.StringIO()
        fieldnames = ["timestamp", "agent_name", "action_type", "target_zone", "rationale"]

        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for a in farm.action_history:
            writer.writerow({
                "timestamp": a.timestamp,
                "agent_name": a.agent_name,
                "action_type": a.action_type,
                "target_zone": a.target_zone or "",
                "rationale": a.rationale,
            })

        return output.getvalue()

    @staticmethod
    def export_summary_dict(farm: FarmDigitalTwin) -> Dict[str, Any]:
        """
        Aggregates farm-wide summary statistics (mean moisture, NDVI, crop distribution).
        """
        total_zones = len(farm.zones)
        if total_zones == 0:
            return {
                "farm_id": farm.farm_id,
                "name": farm.name,
                "total_zones": 0,
                "mean_soil_moisture_pct": 0.0,
                "mean_ndvi": 0.0,
                "crop_distribution": {},
                "health_distribution": {},
            }

        avg_moisture = sum(z.soil_moisture_pct for z in farm.zones) / total_zones
        avg_ndvi = sum(z.ndvi for z in farm.zones) / total_zones
        avg_temp = sum(z.soil_temp_c for z in farm.zones) / total_zones

        crop_counts: Dict[str, int] = {}
        health_counts: Dict[str, int] = {}

        for z in farm.zones:
            crop_counts[z.crop_type] = crop_counts.get(z.crop_type, 0) + 1
            health_counts[z.health_status] = health_counts.get(z.health_status, 0) + 1

        return {
            "farm_id": farm.farm_id,
            "name": farm.name,
            "total_zones": total_zones,
            "mean_soil_moisture_pct": round(avg_moisture, 2),
            "mean_ndvi": round(avg_ndvi, 4),
            "mean_soil_temp_c": round(avg_temp, 2),
            "crop_distribution": crop_counts,
            "health_distribution": health_counts,
            "total_actions_logged": len(farm.action_history),
        }
