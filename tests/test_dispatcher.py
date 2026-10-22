"""
Unit tests for Action Dispatcher & Cryptographic Audit Ledger (Task 3.3)
"""
import pytest
from backend.core.twin_state import create_default_farm
from backend.core.dispatcher import ActionDispatcher


@pytest.fixture
def farm():
    return create_default_farm(width=3, height=3)


def test_enqueue_actions():
    dispatcher = ActionDispatcher()
    assert len(dispatcher.action_queue) == 0

    size1 = dispatcher.enqueue({"type": "irrigate_zone", "zone_id": "Z_0_0", "volume_mm": 15.0})
    size2 = dispatcher.enqueue({"type": "fertilize", "zone_id": "Z_1_1"})

    assert size1 == 1
    assert size2 == 2
    assert len(dispatcher.action_queue) == 2


def test_execute_irrigation_action(farm):
    dispatcher = ActionDispatcher()
    zone = farm.get_zone("Z_2_1")  # Pre-configured as water_stressed in default farm
    assert zone.health_status == "water_stressed"
    initial_moisture = zone.soil_moisture_pct

    dispatcher.enqueue({
        "type": "irrigate_zone",
        "zone_id": "Z_2_1",
        "volume_mm": 20.0,
        "agent_name": "IrrigationAgent"
    })

    receipts = dispatcher.execute_pending(farm)

    assert len(receipts) == 1
    assert receipts[0].status == "SUCCESS_IRRIGATED"
    assert zone.soil_moisture_pct > initial_moisture
    assert zone.health_status == "healthy"
    assert len(farm.action_history) == 1


def test_execute_fertilization_action(farm):
    dispatcher = ActionDispatcher()
    zone = farm.get_zone("Z_0_0")
    initial_ndvi = zone.ndvi

    dispatcher.enqueue({
        "type": "fertilize",
        "zone_id": "Z_0_0",
        "agent_name": "AgronomistAgent"
    })

    receipts = dispatcher.execute_pending(farm)

    assert len(receipts) == 1
    assert receipts[0].status == "SUCCESS_FERTILIZED"
    assert zone.ndvi >= initial_ndvi


def test_cryptographic_audit_ledger_integrity(farm):
    dispatcher = ActionDispatcher()

    # Dispatch multiple actions
    for i in range(5):
        dispatcher.enqueue({
            "type": "irrigate_zone",
            "zone_id": f"Z_{i % 3}_{i % 3}",
            "volume_mm": 10.0 + i
        })

    receipts = dispatcher.execute_pending(farm)
    assert len(receipts) == 5

    # Ledger must verify true
    assert dispatcher.verify_ledger_integrity() is True

    # Check hash chaining: each entry's prev_hash matches prior entry_hash
    for idx in range(1, len(receipts)):
        assert receipts[idx].prev_hash == receipts[idx - 1].entry_hash


def test_anti_tampering_audit_detection(farm):
    dispatcher = ActionDispatcher()
    dispatcher.enqueue({"type": "irrigate_zone", "zone_id": "Z_0_0", "volume_mm": 10.0})
    dispatcher.enqueue({"type": "irrigate_zone", "zone_id": "Z_1_1", "volume_mm": 15.0})
    dispatcher.execute_pending(farm)

    assert dispatcher.verify_ledger_integrity() is True

    # Malicious tampering of second receipt parameter
    dispatcher.audit_ledger[1].parameters["volume_mm"] = 999.0

    # Tampering should be immediately caught by SHA-256 verification
    assert dispatcher.verify_ledger_integrity() is False
