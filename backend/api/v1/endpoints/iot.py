"""
LoRaWAN IoT Gateway REST API Endpoints (v1).

Handles binary uplink frame ingestion from field sensor nodes,
CRC integrity validation, and real-time state synchronization with the Digital Twin.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin
from backend.ingestion.lorawan_codec import LoRaWANCodec, LoRaTelemetryPacket


router = APIRouter(prefix="/iot", tags=["IoT & LoRaWAN Gateway"])


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


class LoRaUplinkRequest(BaseModel):
    """LoRaWAN uplink payload wrapper received from outdoor gateway."""
    payload_hex: str = Field(..., description="12-byte hex-encoded binary payload (24 hex characters)")
    dev_eui: Optional[str] = Field("a84041000182a450", description="64-bit IEEE device identifier")
    rssi: Optional[int] = Field(-78, description="Signal strength indicator in dBm")
    snr: Optional[float] = Field(9.2, description="Signal-to-noise ratio in dB")
    f_port: int = Field(1, ge=1, le=223)


class LoRaSimulateRequest(BaseModel):
    """Request model for testing sensor node telemetry transmissions."""
    x: int = Field(..., ge=0, le=15)
    y: int = Field(..., ge=0, le=15)
    soil_moisture_pct: float = Field(..., ge=0.0, le=100.0)
    soil_temp_c: float = Field(22.5, ge=-20.0, le=80.0)
    soil_ec_us_cm: float = Field(1200.0, ge=0.0)
    battery_mv: int = Field(3700, ge=2000, le=4500)
    packet_type: str = Field("telemetry", description="telemetry, emergency, or heartbeat")
    solar_charging: bool = False
    low_moisture_alert: bool = False


@router.post("/lorawan/uplink")
async def ingest_lorawan_uplink(
    req: LoRaUplinkRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Ingests and decodes a 12-byte packed binary LoRaWAN uplink frame."""
    try:
        raw_bytes = bytes.fromhex(req.payload_hex.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid hex payload: {str(e)}")

    try:
        packet: LoRaTelemetryPacket = LoRaWANCodec.decode_payload(
            payload=raw_bytes,
            rssi_dbm=req.rssi,
            snr_db=req.snr
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"LoRaWAN frame decoding error: {str(e)}")

    applied = LoRaWANCodec.apply_to_twin(packet, farm)

    return {
        "status": "success",
        "dev_eui": req.dev_eui,
        "payload_bytes": len(raw_bytes),
        "packet": packet.model_dump(),
        "applied_to_twin": applied
    }


@router.post("/lorawan/simulate")
async def simulate_lorawan_node(
    req: LoRaSimulateRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Encodes sensor values into LoRaWAN binary format and delivers to Digital Twin."""
    payload_bytes = LoRaWANCodec.encode_payload(
        x=req.x,
        y=req.y,
        soil_moisture_pct=req.soil_moisture_pct,
        soil_temp_c=req.soil_temp_c,
        soil_ec_us_cm=req.soil_ec_us_cm,
        battery_mv=req.battery_mv,
        packet_type=req.packet_type,
        solar_charging=req.solar_charging,
        low_moisture_alert=req.low_moisture_alert
    )

    packet = LoRaWANCodec.decode_payload(payload_bytes, rssi_dbm=-75, snr_db=10.5)
    applied = LoRaWANCodec.apply_to_twin(packet, farm)

    return {
        "status": "simulated",
        "hex_payload": payload_bytes.hex().upper(),
        "payload_bytes": len(payload_bytes),
        "packet": packet.model_dump(),
        "applied_to_twin": applied
    }


@router.get("/gateway/status")
async def get_gateway_status(
    farm: FarmDigitalTwin = Depends(get_farm_state)
) -> Dict[str, Any]:
    """Retrieves operational status of the on-site agricultural LoRaWAN gateway."""
    return {
        "gateway_id": "gw-dalat-central-01",
        "model": "Dragino DLOS8 Outdoor IP67",
        "frequency_plan": "AS923-2 (Vietnam 920-923 MHz)",
        "channel_count": 8,
        "status": "online",
        "managed_zones_count": len(farm.zones),
        "duty_cycle_current_pct": 0.38,
        "duty_cycle_limit_pct": 1.0,
        "coordinates": {
            "latitude": farm.latitude,
            "longitude": farm.longitude
        }
    }
