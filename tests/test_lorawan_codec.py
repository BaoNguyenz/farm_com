"""
Unit tests for LoRaWAN Agricultural Telemetry Codec.
Tests binary serialization roundtrips, CRC-8 integrity verification,
fault injection, coordinate packing, and digital twin synchronization.
"""

import pytest
from backend.ingestion.lorawan_codec import LoRaWANCodec, LoRaTelemetryPacket
from backend.core.twin_state import create_default_farm


def test_lorawan_encode_decode_roundtrip():
    payload = LoRaWANCodec.encode_payload(
        x=2,
        y=3,
        soil_moisture_pct=64.75,
        soil_temp_c=23.40,
        soil_ec_us_cm=1250.0,
        battery_mv=3780,
        packet_type="telemetry",
        solar_charging=True,
        low_moisture_alert=False
    )

    assert len(payload) == 12

    packet = LoRaWANCodec.decode_payload(payload, rssi_dbm=-82, snr_db=9.5)
    assert isinstance(packet, LoRaTelemetryPacket)
    assert packet.zone_id == "Z_2_3"
    assert packet.x == 2
    assert packet.y == 3
    assert packet.packet_type == "telemetry"
    assert abs(packet.soil_moisture_pct - 64.75) < 0.01
    assert abs(packet.soil_temp_c - 23.40) < 0.01
    assert packet.soil_ec_us_cm == 1250.0
    assert packet.battery_mv == 3780
    assert packet.solar_charging is True
    assert packet.low_moisture_alert is False
    assert packet.rssi_dbm == -82
    assert packet.snr_db == 9.5


def test_lorawan_coordinate_packing():
    # Test boundary coordinates
    for x, y in [(0, 0), (1, 2), (4, 4), (15, 15)]:
        payload = LoRaWANCodec.encode_payload(
            x=x, y=y,
            soil_moisture_pct=50.0,
            soil_temp_c=20.0,
            soil_ec_us_cm=800.0,
            battery_mv=3300
        )
        packet = LoRaWANCodec.decode_payload(payload)
        assert packet.x == x
        assert packet.y == y
        assert packet.zone_id == f"Z_{x}_{y}"


def test_lorawan_alert_flags():
    payload = LoRaWANCodec.encode_payload(
        x=1,
        y=1,
        soil_moisture_pct=22.5,
        soil_temp_c=34.2,
        soil_ec_us_cm=3200.0,
        battery_mv=2900,
        packet_type="emergency",
        solar_charging=False,
        sensor_fault=False,
        low_moisture_alert=True,
        high_salinity_alert=True
    )

    packet = LoRaWANCodec.decode_payload(payload)
    assert packet.packet_type == "emergency"
    assert packet.low_moisture_alert is True
    assert packet.high_salinity_alert is True
    assert packet.solar_charging is False


def test_lorawan_crc_corruption_detection():
    payload = bytearray(LoRaWANCodec.encode_payload(
        x=0, y=1,
        soil_moisture_pct=45.0,
        soil_temp_c=18.5,
        soil_ec_us_cm=500.0,
        battery_mv=3600
    ))

    # Corrupt payload byte 3
    payload[3] ^= 0xFF

    with pytest.raises(ValueError, match="CRC-8 verification failed"):
        LoRaWANCodec.decode_payload(bytes(payload))


def test_lorawan_invalid_length_detection():
    with pytest.raises(ValueError, match="Invalid LoRaWAN payload length"):
        LoRaWANCodec.decode_payload(b"short")

    with pytest.raises(ValueError, match="Invalid LoRaWAN payload length"):
        LoRaWANCodec.decode_payload(b"this_payload_is_17_bytes_")


def test_lorawan_apply_to_twin():
    farm = create_default_farm(width=3, height=3)
    target_zone = farm.get_zone("Z_1_1")
    assert target_zone is not None

    packet = LoRaTelemetryPacket(
        zone_id="Z_1_1",
        x=1,
        y=1,
        packet_type="emergency",
        soil_moisture_pct=26.4,
        soil_temp_c=28.5,
        soil_ec_us_cm=1100.0,
        battery_mv=3500,
        low_moisture_alert=True
    )

    success = LoRaWANCodec.apply_to_twin(packet, farm)
    assert success is True
    assert target_zone.soil_moisture_pct == 26.4
    assert target_zone.soil_temp_c == 28.5
    assert target_zone.health_status == "water_stressed"
