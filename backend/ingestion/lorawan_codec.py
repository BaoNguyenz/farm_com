"""
LoRaWAN Agricultural Telemetry Codec (AS923 / EU868).

Implements packed 12-byte binary serialization and deserialization for low-power
field sensor nodes (ESP32-S3 / nRF52 + SX1262), ensuring compliance with regional
duty cycle limits and sub-second transmission airtime.
"""

from typing import Optional, Dict
import struct
import time
from pydantic import BaseModel, Field

from backend.core.twin_state import FarmDigitalTwin, PlotZone


class LoRaTelemetryPacket(BaseModel):
    """Decoded high-precision telemetry representation from a LoRaWAN field node."""
    zone_id: str = Field(..., description="Zone identifier, e.g. Z_1_2")
    x: int
    y: int
    packet_type: str = Field("telemetry", description="Packet classification: telemetry, emergency, heartbeat")
    soil_moisture_pct: float = Field(..., ge=0.0, le=100.0)
    soil_temp_c: float = Field(..., ge=-20.0, le=80.0)
    soil_ec_us_cm: float = Field(..., ge=0.0, description="Electrical Conductivity in microSiemens/cm")
    battery_mv: int = Field(..., ge=1500, le=5000, description="Battery voltage in millivolts")
    solar_charging: bool = False
    sensor_fault: bool = False
    low_moisture_alert: bool = False
    high_salinity_alert: bool = False
    rssi_dbm: Optional[int] = Field(None, description="Received Signal Strength Indicator")
    snr_db: Optional[float] = Field(None, description="Signal-to-Noise Ratio")
    timestamp: float = Field(default_factory=time.time)


class LoRaWANCodec:
    """
    Encoder and decoder for 12-byte packed binary LoRaWAN agricultural payloads.

    Packet Structure (12 bytes):
      [0]   uint8   packet_type (0x01: Telemetry, 0x02: Emergency, 0x03: Heartbeat)
      [1]   uint8   spatial_coordinate: (x << 4) | (y & 0x0F)
      [2:4] uint16  soil_moisture_pct * 100 (big-endian)
      [4:6] int16   soil_temp_c * 100 (big-endian)
      [6:8] uint16  soil_ec_us_cm (big-endian)
      [8:10]uint16  battery_mv (big-endian)
      [10]  uint8   flags:
                    bit 0: solar_charging
                    bit 1: sensor_fault
                    bit 2: low_moisture_alert
                    bit 3: high_salinity_alert
      [11]  uint8   CRC-8 checksum (Dallas/Maxim polynomial: x^8 + x^5 + x^4 + 1)
    """

    TYPE_MAP: Dict[int, str] = {
        0x01: "telemetry",
        0x02: "emergency",
        0x03: "heartbeat"
    }
    REVERSE_TYPE_MAP: Dict[str, int] = {v: k for k, v in TYPE_MAP.items()}

    @staticmethod
    def calculate_crc8(data: bytes) -> int:
        """Calculates Dallas/Maxim CRC-8 (polynomial 0x31, initial 0x00)."""
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ 0x31) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
        return crc

    @classmethod
    def encode_payload(
        cls,
        x: int,
        y: int,
        soil_moisture_pct: float,
        soil_temp_c: float,
        soil_ec_us_cm: float,
        battery_mv: int,
        packet_type: str = "telemetry",
        solar_charging: bool = False,
        sensor_fault: bool = False,
        low_moisture_alert: bool = False,
        high_salinity_alert: bool = False
    ) -> bytes:
        """Encodes sensor readings into a 12-byte packed binary frame."""
        p_type = cls.REVERSE_TYPE_MAP.get(packet_type, 0x01)
        spatial_coord = ((x & 0x0F) << 4) | (y & 0x0F)
        moisture_raw = int(round(max(0.0, min(100.0, soil_moisture_pct)) * 100))
        temp_raw = int(round(max(-20.0, min(80.0, soil_temp_c)) * 100))
        ec_raw = int(round(max(0.0, min(65535.0, soil_ec_us_cm))))
        batt_raw = int(round(max(0, min(65535, battery_mv))))

        flags = 0
        if solar_charging:
            flags |= (1 << 0)
        if sensor_fault:
            flags |= (1 << 1)
        if low_moisture_alert:
            flags |= (1 << 2)
        if high_salinity_alert:
            flags |= (1 << 3)

        payload_11 = struct.pack(
            ">BBHhHHB",
            p_type,
            spatial_coord,
            moisture_raw,
            temp_raw,
            ec_raw,
            batt_raw,
            flags
        )
        crc = cls.calculate_crc8(payload_11)
        return payload_11 + bytes([crc])

    @classmethod
    def decode_payload(
        cls,
        payload: bytes,
        rssi_dbm: Optional[int] = None,
        snr_db: Optional[float] = None
    ) -> LoRaTelemetryPacket:
        """
        Decodes and validates a 12-byte LoRaWAN binary frame.
        Raises ValueError if payload length or CRC checksum is invalid.
        """
        if len(payload) != 12:
            raise ValueError(f"Invalid LoRaWAN payload length: expected 12 bytes, got {len(payload)} bytes.")

        body = payload[:11]
        received_crc = payload[11]
        computed_crc = cls.calculate_crc8(body)

        if received_crc != computed_crc:
            raise ValueError(f"CRC-8 verification failed: computed 0x{computed_crc:02X}, received 0x{received_crc:02X}.")

        p_type, spatial_coord, moisture_raw, temp_raw, ec_raw, batt_raw, flags = struct.unpack(
            ">BBHhHHB",
            body
        )

        x = (spatial_coord >> 4) & 0x0F
        y = spatial_coord & 0x0F
        zone_id = f"Z_{x}_{y}"

        packet_type_str = cls.TYPE_MAP.get(p_type, "telemetry")

        return LoRaTelemetryPacket(
            zone_id=zone_id,
            x=x,
            y=y,
            packet_type=packet_type_str,
            soil_moisture_pct=round(moisture_raw / 100.0, 2),
            soil_temp_c=round(temp_raw / 100.0, 2),
            soil_ec_us_cm=float(ec_raw),
            battery_mv=batt_raw,
            solar_charging=bool(flags & (1 << 0)),
            sensor_fault=bool(flags & (1 << 1)),
            low_moisture_alert=bool(flags & (1 << 2)),
            high_salinity_alert=bool(flags & (1 << 3)),
            rssi_dbm=rssi_dbm,
            snr_db=snr_db,
            timestamp=time.time()
        )

    @classmethod
    def apply_to_twin(cls, packet: LoRaTelemetryPacket, farm: FarmDigitalTwin) -> bool:
        """Applies decoded telemetry measurements directly to the Digital Twin zone."""
        zone: Optional[PlotZone] = farm.get_zone(packet.zone_id)
        if not zone:
            return False

        zone.soil_moisture_pct = packet.soil_moisture_pct
        zone.soil_temp_c = packet.soil_temp_c

        # Update health status if alert flags present
        if packet.low_moisture_alert or packet.soil_moisture_pct < 35.0:
            zone.health_status = "water_stressed"
        elif packet.high_salinity_alert:
            zone.health_status = "salinity_risk"
        elif zone.health_status in ("water_stressed", "salinity_risk") and packet.soil_moisture_pct >= 50.0:
            zone.health_status = "recovering"

        return True
