"""
Aerial Drone Autonomous Multispectral Scouting & High-Resolution Canopy Computer Vision Engine.

Models UAV (Unmanned Aerial Vehicle) flight missions across farm zones, simulating:
- Multispectral 5-band sensors (Red, Green, Blue, RedEdge, Near-Infrared)
- Visible Atmospherically Resistant Index (VARI) for RGB orthomosaics
- Normalized Difference Red Edge (NDRE) for dense canopy nitrogen & chlorophyll
- Sub-centimeter canopy cover fraction (f_cover %), plant emergence gaps, and weed clusters
"""

from datetime import UTC, datetime
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.core.twin_state import PlotZone


class DroneMissionStatus(str, Enum):
    """UAV Flight State."""
    IDLE = "idle"
    IN_FLIGHT = "in_flight"
    SCOUTING = "scouting"
    RETURNING = "returning"
    COMPLETED = "completed"
    ABORTED_LOW_BATTERY = "aborted_low_battery"


class SpectralBandReflectance(BaseModel):
    """Calibrated surface reflectance across 5 UAV multispectral channels [0.0, 1.0]."""
    blue: float = Field(..., ge=0.0, le=1.0, description="Blue band ~475 nm")
    green: float = Field(..., ge=0.0, le=1.0, description="Green band ~560 nm")
    red: float = Field(..., ge=0.0, le=1.0, description="Red band ~668 nm")
    red_edge: float = Field(..., ge=0.0, le=1.0, description="RedEdge band ~717 nm")
    nir: float = Field(..., ge=0.0, le=1.0, description="Near-Infrared band ~840 nm")


class ZoneScoutingSurvey(BaseModel):
    """Computer vision analytics extracted from aerial orthomosaic tiles over a plot zone."""
    zone_id: str
    crop_type: str
    canopy_cover_pct: float = Field(..., ge=0.0, le=100.0, description="Fraction of soil covered by green foliage")
    mean_vari: float = Field(..., description="Visible Atmospherically Resistant Index")
    mean_ndre: float = Field(..., description="Normalized Difference Red Edge index")
    estimated_plant_count: int = Field(..., ge=0, description="Detected plant crowns from point-cloud")
    emergence_gap_count: int = Field(..., ge=0, description="Significant germination / emergence gaps")
    chlorosis_hotspots: int = Field(..., ge=0, description="Clusters of nitrogen deficiency / yellowing")
    weed_pressure_score: float = Field(..., ge=0.0, le=1.0, description="Inter-row weed infestation index")
    scouting_urgency: str = Field("nominal", description="nominal, warning, or critical")
    actionable_finding: str


class DroneScoutingReport(BaseModel):
    """Aggregated mission summary for autonomous farm dispatch and agronomist ingestion."""
    mission_id: str
    timestamp_utc: str
    status: DroneMissionStatus
    flight_altitude_m: float
    total_area_scouted_ha: float
    flight_duration_minutes: float
    battery_consumed_pct: float
    zone_surveys: list[ZoneScoutingSurvey]
    critical_anomalies: list[str]


class DroneScoutingEngine:
    """
    Simulates high-precision UAV autonomous scouting flights, orthomosaic analysis,
    and biophysical canopy index extraction.
    """

    # Battery consumption rate per hectare at standard survey altitude (30m AGL)
    BATTERY_PCT_PER_HA: ClassVar[float] = 4.5
    FLIGHT_MINUTES_PER_HA: ClassVar[float] = 3.2

    @classmethod
    def compute_spectral_indices(cls, bands: SpectralBandReflectance) -> dict[str, float]:
        """
        Calculate VARI, NDRE, and standard NDVI from multispectral surface reflectance.
        """
        # VARI = (Green - Red) / (Green + Red - Blue)
        vari_denom = bands.green + bands.red - bands.blue
        vari = (bands.green - bands.red) / vari_denom if abs(vari_denom) > 1e-5 else 0.0

        # NDRE = (NIR - RedEdge) / (NIR + RedEdge)
        ndre_denom = bands.nir + bands.red_edge
        ndre = (bands.nir - bands.red_edge) / ndre_denom if abs(ndre_denom) > 1e-5 else 0.0

        # NDVI = (NIR - Red) / (NIR + Red)
        ndvi_denom = bands.nir + bands.red
        ndvi = (bands.nir - bands.red) / ndvi_denom if abs(ndvi_denom) > 1e-5 else 0.0

        return {
            "vari": round(max(-1.0, min(1.0, vari)), 4),
            "ndre": round(max(-1.0, min(1.0, ndre)), 4),
            "ndvi": round(max(-1.0, min(1.0, ndvi)), 4),
        }

    def analyze_zone(
        self,
        zone: PlotZone,
        bands: SpectralBandReflectance | None = None,
    ) -> ZoneScoutingSurvey:
        """
        Extract high-resolution canopy traits and anomaly hotspots for a zone.
        Synthesizes realistic spectral values if raw reflectance is not provided.
        """
        if bands is None:
            # Synthesize reflectance correlated with zone digital twin state
            if zone.health_status == "optimal":
                bands = SpectralBandReflectance(blue=0.03, green=0.12, red=0.04, red_edge=0.28, nir=0.62)
            elif zone.health_status == "diseased":
                bands = SpectralBandReflectance(blue=0.06, green=0.09, red=0.08, red_edge=0.18, nir=0.34)
            else:  # stressed
                bands = SpectralBandReflectance(blue=0.05, green=0.08, red=0.06, red_edge=0.20, nir=0.42)

        indices = self.compute_spectral_indices(bands)
        vari = indices["vari"]
        ndre = indices["ndre"]

        # Canopy cover fraction f_cover estimation based on NDRE & NDVI
        f_cover = min(98.5, max(15.0, round(zone.ndvi * 115.0 - 5.0, 1)))

        # Stand count estimation: ~3.5 to 5.0 plants per m2 based on area
        expected_plants = int(zone.area_m2 * 4.2)
        stand_establishment_pct = min(1.0, max(0.5, (f_cover / 100.0) * 1.1))
        plant_count = int(expected_plants * stand_establishment_pct)

        # Gap and chlorosis detection
        emergence_gaps = max(0, int((1.0 - (f_cover / 100.0)) * (zone.area_m2 / 120.0)))
        chlorosis_hotspots = 0
        if ndre < 0.25:
            chlorosis_hotspots = max(1, int((0.30 - ndre) * 20))

        # Weed pressure score from inter-row VARI variance
        weed_score = round(max(0.05, min(0.85, (100.0 - f_cover) / 250.0 + (vari * 0.15))), 3)

        urgency = "nominal"
        finding = f"Zone {zone.id} ({zone.crop_type}) canopy vigor is nominal (Cover: {f_cover}%, NDRE: {ndre})."

        if chlorosis_hotspots >= 2 or emergence_gaps >= 4 or zone.health_status == "diseased":
            urgency = "critical"
            finding = (
                f"CRITICAL: {chlorosis_hotspots} chlorotic patches & {emergence_gaps} emergence gaps in "
                f"Zone {zone.id}. Immediate targeted foliar intervention recommended."
            )
        elif chlorosis_hotspots > 0 or emergence_gaps > 0 or weed_score > 0.40:
            urgency = "warning"
            finding = (
                f"WARNING: Minor canopy variation detected in Zone {zone.id} "
                f"(Weed index: {weed_score}, Chlorosis: {chlorosis_hotspots})."
            )

        return ZoneScoutingSurvey(
            zone_id=zone.id,
            crop_type=zone.crop_type,
            canopy_cover_pct=f_cover,
            mean_vari=vari,
            mean_ndre=ndre,
            estimated_plant_count=plant_count,
            emergence_gap_count=emergence_gaps,
            chlorosis_hotspots=chlorosis_hotspots,
            weed_pressure_score=weed_score,
            scouting_urgency=urgency,
            actionable_finding=finding,
        )

    def simulate_mission(
        self,
        zones: list[PlotZone],
        mission_id: str = "UAV-SCOUT-01",
        altitude_m: float = 30.0,
        initial_battery_pct: float = 95.0,
    ) -> DroneScoutingReport:
        """
        Execute an autonomous scouting mission over target zones.
        Ensures battery safety margin (RTH threshold 20%).
        """
        total_area_m2 = sum(z.area_m2 for z in zones)
        total_ha = total_area_m2 / 10000.0

        flight_duration = round(total_ha * self.FLIGHT_MINUTES_PER_HA, 1)
        battery_needed = round(total_ha * self.BATTERY_PCT_PER_HA, 1)

        status = DroneMissionStatus.COMPLETED
        if (initial_battery_pct - battery_needed) < 20.0:
            status = DroneMissionStatus.ABORTED_LOW_BATTERY

        surveys: list[ZoneScoutingSurvey] = []
        critical_anomalies: list[str] = []

        for z in zones:
            survey = self.analyze_zone(z)
            surveys.append(survey)
            if survey.scouting_urgency == "critical":
                critical_anomalies.append(f"{z.id}: {survey.actionable_finding}")

        return DroneScoutingReport(
            mission_id=mission_id,
            timestamp_utc=datetime.now(UTC).isoformat(),
            status=status,
            flight_altitude_m=altitude_m,
            total_area_scouted_ha=round(total_ha, 3),
            flight_duration_minutes=flight_duration,
            battery_consumed_pct=battery_needed,
            zone_surveys=surveys,
            critical_anomalies=critical_anomalies,
        )
