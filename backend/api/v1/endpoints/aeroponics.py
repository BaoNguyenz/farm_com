"""
REST API Endpoints for Vertical Aeroponics Ultrasonic Misting & LED Photobiology.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.agents.agronomist import AgronomistAgent
from backend.agents.market import MarketAgent
from backend.core.aeroponics_mist import (
    AeroponicChamberState,
    AeroponicsMistEngine,
    AtomizerMode,
)
from backend.core.led_photobiology import (
    LEDPhotobiologyEngine,
    LEDSpectrumState,
    PhotobiologyRecipe,
)

router = APIRouter(prefix="/aeroponics", tags=["Vertical Aeroponics & LED Photobiology"])

_mist_engine = AeroponicsMistEngine()
_led_engine = LEDPhotobiologyEngine()
_agronomist = AgronomistAgent()
_market = MarketAgent()


class SimulateMistRequest(BaseModel):
    """Payload to evaluate aeroponic root-chamber misting & ion uptake."""
    atomizer_mode: AtomizerMode = AtomizerMode.ULTRASONIC_PIEZO_1_7MHZ
    root_chamber_temp_c: float = Field(21.0, ge=10.0, le=38.0)
    root_chamber_rh_pct: float = Field(92.0, ge=40.0, le=100.0)
    nitrate_ppm: float = Field(140.0, ge=0.0, le=500.0)
    potassium_ppm: float = Field(180.0, ge=0.0, le=500.0)


class TuneSpectrumRequest(BaseModel):
    """Payload to tune LED spectrum and supplemental DLI."""
    recipe: PhotobiologyRecipe = PhotobiologyRecipe.FLOWERING_ANTHOCYANIN
    target_dli_mol_m2_day: float = Field(18.0, ge=5.0, le=35.0)
    solar_dli_mol_m2_day: float = Field(10.5, ge=0.0, le=35.0)
    photoperiod_hours: float = Field(14.0, ge=4.0, le=24.0)
    custom_far_red_pct: float | None = Field(None, ge=1.0, le=40.0)


@router.get("/telemetry")
def get_aeroponics_telemetry() -> dict[str, Any]:
    """Retrieves live ultrasonic aeroponic chamber, LED DLI spectrum, and ROI."""
    chamber = _mist_engine.evaluate_chamber()
    spectrum = _led_engine.tune_supplemental_lighting()
    audit = _agronomist.audit_aeroponics_photobiology(
        root_chamber_temp_c=chamber.root_chamber_temp_c,
        dissolved_oxygen_mg_l=chamber.dissolved_oxygen_mg_l,
        phytochrome_pss=spectrum.phytochrome_pss,
        shade_avoidance_risk=spectrum.shade_avoidance_risk,
    )
    economics = _market.evaluate_aeroponics_led_roi(
        canopy_area_m2=120.0,
        energy_kwh_per_m2_day=spectrum.energy_kwh_per_m2_day,
    )

    return {
        "system_status": "VERTICAL_AEROPONICS_OPTIMAL",
        "chamber": chamber.model_dump(),
        "led_spectrum": spectrum.model_dump(),
        "chamber_audit": audit,
        "economics": economics,
    }


@router.post("/simulate-mist", response_model=AeroponicChamberState)
def simulate_aeroponic_mist(req: SimulateMistRequest) -> AeroponicChamberState:
    """Simulates ultrasonic droplet diameter, dissolved oxygen, and ion uptake."""
    return _mist_engine.evaluate_chamber(
        atomizer_mode=req.atomizer_mode,
        root_chamber_temp_c=req.root_chamber_temp_c,
        root_chamber_rh_pct=req.root_chamber_rh_pct,
        nitrate_ppm=req.nitrate_ppm,
        potassium_ppm=req.potassium_ppm,
    )


@router.post("/tune-spectrum", response_model=LEDSpectrumState)
def tune_led_spectrum(req: TuneSpectrumRequest) -> LEDSpectrumState:
    """Computes supplemental PPFD, LED power density, and phytochrome PSS."""
    return _led_engine.tune_supplemental_lighting(
        recipe=req.recipe,
        target_dli_mol_m2_day=req.target_dli_mol_m2_day,
        solar_dli_mol_m2_day=req.solar_dli_mol_m2_day,
        photoperiod_hours=req.photoperiod_hours,
        custom_far_red_pct=req.custom_far_red_pct,
    )
