"""
Bio-Acoustic Pollination Monitoring & Bumblebee Buzz Resonance REST Endpoints.
Provides floral visitation telemetry, fruit deformation risk audits, and acoustic sonication classification.
"""
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.core.pollination import (
    BioAcousticPollinationEngine,
    BuzzPollinationEvent,
    FarmPollinationReport,
    ZonePollinationAudit,
)
from backend.core.twin_state import FarmDigitalTwin, PlotZone, WeatherTelemetry

router = APIRouter(prefix="/pollination", tags=["pollination"])
pollination_engine = BioAcousticPollinationEngine()


class AcousticBuzzSimulationRequest(BaseModel):
    frequency_hz: float = Field(..., ge=100.0, le=1000.0, description="Measured audio acoustic frequency in Hz")
    duration_seconds: float = Field(..., ge=0.05, le=10.0, description="Acoustic burst duration in seconds")
    amplitude_db: float = Field(-18.0, description="Audio signal amplitude in dBFS")
    zone_id: str = Field("ZONE_1", description="Greenhouse plot zone identifier")


class AcousticBuzzSimulationResponse(BaseModel):
    is_valid_floral_sonication: bool
    classification: str
    target_resonance_range_hz: str
    event: BuzzPollinationEvent


def _create_default_twin() -> FarmDigitalTwin:
    return FarmDigitalTwin(
        farm_id="FARM-CEA-DEFAULT",
        zones=[
            PlotZone(
                id="ZONE_GH_1",
                x=0,
                y=0,
                crop_type="Strawberries",
                growth_stage="flowering",
                soil_moisture_pct=60.0,
                soil_temp_c=20.0,
                soil_ph=6.2,
                ndvi=0.82,
                ndwi=0.35,
                health_status="optimal",
                accumulated_gdd=350.0,
            ),
            PlotZone(
                id="ZONE_GH_2",
                x=1,
                y=0,
                crop_type="Strawberries",
                growth_stage="fruiting",
                soil_moisture_pct=58.0,
                soil_temp_c=20.5,
                soil_ph=6.3,
                ndvi=0.79,
                ndwi=0.32,
                health_status="optimal",
                accumulated_gdd=380.0,
            ),
            PlotZone(
                id="ZONE_GH_3",
                x=2,
                y=0,
                crop_type="Bell Pepper",
                growth_stage="flowering",
                soil_moisture_pct=65.0,
                soil_temp_c=21.0,
                soil_ph=6.4,
                ndvi=0.85,
                ndwi=0.36,
                health_status="optimal",
                accumulated_gdd=410.0,
            ),
        ],
        current_weather=WeatherTelemetry(
            temp_c=23.5,
            humidity_percent=68.0,
            solar_radiation_mj=18.5,
            wind_speed_mps=1.8,
            rain_probability=0.0,
        ),
    )


@router.get("/status", response_model=FarmPollinationReport)
def get_farm_pollination_status() -> FarmPollinationReport:
    """
    Returns consolidated farm-wide bio-acoustic pollination index,
    average floral visits, and fruit set deformation risk.
    """
    twin = _create_default_twin()
    return pollination_engine.audit_farm(twin)


@router.get("/zone/{zone_id}", response_model=ZonePollinationAudit)
def get_zone_pollination_audit(
    zone_id: str,
    flower_count_per_m2: int = Query(40, ge=1, le=500),
    buzz_events_per_hour: int = Query(120, ge=0, le=2000),
    ambient_temp_c: float = Query(23.0, ge=0.0, le=50.0),
) -> ZonePollinationAudit:
    """
    Audits a single plot zone for floral sonication visits, fruit deformation risk,
    and thermal foraging cessation.
    """
    return pollination_engine.audit_zone(
        zone_id=zone_id,
        flower_count_per_m2=flower_count_per_m2,
        buzz_events_per_hour=buzz_events_per_hour,
        ambient_temp_c=ambient_temp_c,
    )


@router.post("/simulate-buzz", response_model=AcousticBuzzSimulationResponse)
def simulate_acoustic_buzz(payload: AcousticBuzzSimulationRequest) -> AcousticBuzzSimulationResponse:
    """
    Classifies raw microphone frequency events into floral buzz pollination vs regular wingbeat or ambient noise.
    """
    is_sonication = pollination_engine.analyze_acoustic_signature(
        frequency_hz=payload.frequency_hz,
        duration_seconds=payload.duration_seconds,
    )

    if is_sonication:
        classification = "bombus_floral_sonication"
    elif 130.0 <= payload.frequency_hz <= 220.0:
        classification = "flight_wingbeat"
    else:
        classification = "ambient_or_mechanical_noise"

    event = BuzzPollinationEvent(
        timestamp=time.time(),
        frequency_hz=payload.frequency_hz,
        amplitude_db=payload.amplitude_db,
        duration_seconds=payload.duration_seconds,
        zone_id=payload.zone_id,
    )

    return AcousticBuzzSimulationResponse(
        is_valid_floral_sonication=is_sonication,
        classification=classification,
        target_resonance_range_hz="310 - 390 Hz (duration: 0.4 - 4.0s)",
        event=event,
    )
