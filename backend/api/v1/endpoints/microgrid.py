"""
RESTful Endpoints for Agrivoltaic Micro-Grid & Battery Energy Storage (BESS) Management.
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.microgrid import (
    BatteryStorageSystem,
    MicrogridController,
    MicrogridDispatchResult,
    SolarPVArray,
)

router = APIRouter(prefix="/microgrid", tags=["Microgrid & Energy Management"])

# Global controller instance for farm digital twin
_controller = MicrogridController(
    solar=SolarPVArray(installed_capacity_kwp=25.0, panel_area_m2=120.0),
    battery=BatteryStorageSystem(capacity_kwh=40.0, current_soc=0.70),
)


class MicrogridDispatchRequest(BaseModel):
    """Payload for manual or simulated microgrid energy dispatch step."""
    load_kw: float = Field(..., ge=0.0, description="Farm electrical load in kW (e.g. pumps, chillers)")
    irradiance_w_m2: float = Field(650.0, ge=0.0, description="Solar surface irradiance W/m²")
    ambient_temp_c: float = Field(24.0, description="Ambient air temperature in °C")
    hour_of_day: int | None = Field(None, ge=0, le=23, description="24-hour clock hour (defaults to 12)")
    grid_available: bool = Field(True, description="Whether national EVN grid is energized")
    duration_hours: float = Field(1.0, gt=0.0, le=24.0, description="Duration in hours for dispatch calculation")


@router.get("/status")
def get_microgrid_status() -> dict[str, Any]:
    """
    Retrieve real-time telemetry of solar PV generation and BESS battery status.
    """
    solar = _controller.solar
    bess = _controller.battery

    # Representative midday solar reading (600 W/m2, 24C)
    current_solar_kw = solar.calculate_power(irradiance_w_m2=600.0, ambient_temp_c=24.0)

    return {
        "status": "online",
        "solar_pv": {
            "installed_capacity_kwp": solar.installed_capacity_kwp,
            "panel_area_m2": solar.panel_area_m2,
            "current_power_kw": current_solar_kw,
            "stc_efficiency": solar.stc_efficiency,
        },
        "battery_bess": {
            "capacity_kwh": bess.capacity_kwh,
            "current_soc": round(bess.current_soc, 4),
            "stored_energy_kwh": round(bess.stored_energy_kwh, 2),
            "available_discharge_kwh": round(bess.available_discharge_kwh, 2),
            "available_charge_kwh": round(bess.available_charge_kwh, 2),
            "roundtrip_efficiency": bess.roundtrip_efficiency,
        },
    }


@router.post("/dispatch", response_model=MicrogridDispatchResult)
def dispatch_microgrid_energy(req: MicrogridDispatchRequest) -> MicrogridDispatchResult:
    """
    Calculate optimal power flow dispatch across Solar PV, BESS, and EVN Grid.
    """
    hour = req.hour_of_day if req.hour_of_day is not None else 12

    return _controller.dispatch(
        load_kw=req.load_kw,
        irradiance_w_m2=req.irradiance_w_m2,
        ambient_temp_c=req.ambient_temp_c,
        hour_of_day=hour,
        grid_available=req.grid_available,
        duration_hours=req.duration_hours,
    )


@router.get("/tariffs")
def get_electricity_tariffs() -> dict[str, Any]:
    """
    Retrieve EVN Time-of-Use (TOU) electricity pricing schedule and rates.
    """
    return {
        "currency": "VND",
        "tariffs": {
            "off_peak": {
                "rate_vnd_per_kwh": _controller.TARIFF_RATES[_controller.get_tariff_tier(2)],
                "hours": "22:00 - 04:00",
            },
            "normal": {
                "rate_vnd_per_kwh": _controller.TARIFF_RATES[_controller.get_tariff_tier(14)],
                "hours": "04:00 - 09:30, 11:30 - 17:00, 20:00 - 22:00",
            },
            "peak": {
                "rate_vnd_per_kwh": _controller.TARIFF_RATES[_controller.get_tariff_tier(10)],
                "hours": "09:30 - 11:30, 17:00 - 20:00",
            },
        },
        "grid_carbon_factor_kg_co2e_per_kwh": _controller.GRID_CARBON_FACTOR,
    }
