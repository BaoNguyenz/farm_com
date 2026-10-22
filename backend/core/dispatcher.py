"""
Action Dispatcher & Immutable Audit Ledger.
Provides an action execution queue, action handlers, and cryptographic
hash-chained audit receipts for transparent multi-agent governance.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import hashlib
import json
import time
from backend.core.twin_state import FarmDigitalTwin, ActionLog


@dataclass
class AuditReceipt:
    """Cryptographically verifiable execution record in the audit chain."""
    entry_index: int
    timestamp: float
    action_type: str
    target_zone: Optional[str]
    agent_name: str
    parameters: Dict[str, Any]
    status: str
    prev_hash: str
    entry_hash: str = ""

    def calculate_hash(self) -> str:
        payload = f"{self.entry_index}:{self.timestamp}:{self.action_type}:{self.target_zone}:{self.agent_name}:{json.dumps(self.parameters, sort_keys=True)}:{self.status}:{self.prev_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ActionDispatcher:
    """
    Manages action queues, executes physical actuator changes on PlotZones,
    and maintains an immutable SHA-256 audit ledger.
    """
    def __init__(self):
        self.action_queue: List[Dict[str, Any]] = []
        self.audit_ledger: List[AuditReceipt] = []
        self._genesis_hash: str = "0" * 64

    def enqueue(self, action: Dict[str, Any]) -> int:
        """Enqueues an action for execution. Returns current queue size."""
        self.action_queue.append(action)
        return len(self.action_queue)

    def execute_pending(self, farm: FarmDigitalTwin) -> List[AuditReceipt]:
        """
        Executes all queued actions against the Farm Digital Twin,
        applies state changes, and mints cryptographically chained receipts.
        """
        receipts: List[AuditReceipt] = []

        while self.action_queue:
            act = self.action_queue.pop(0)
            action_type = act.get("type", "unknown")
            zone_id = act.get("zone_id")
            agent = act.get("agent_name", "Commander")
            params = act.get("parameters", {})
            if "volume_mm" in act and "volume_mm" not in params:
                params["volume_mm"] = act["volume_mm"]

            # Apply physical modification
            status = self._apply_action(farm, action_type, zone_id, params)

            # Record in Farm action_history
            farm.action_history.append(
                ActionLog(
                    agent_name=agent,
                    action_type=action_type,
                    target_zone=zone_id,
                    parameters=params,
                    rationale=act.get("rationale", f"Executed {action_type} on {zone_id}")
                )
            )

            # Chain into immutable ledger
            prev_hash = self.audit_ledger[-1].entry_hash if self.audit_ledger else self._genesis_hash
            receipt = AuditReceipt(
                entry_index=len(self.audit_ledger) + 1,
                timestamp=time.time(),
                action_type=action_type,
                target_zone=zone_id,
                agent_name=agent,
                parameters=params,
                status=status,
                prev_hash=prev_hash
            )
            receipt.entry_hash = receipt.calculate_hash()
            self.audit_ledger.append(receipt)
            receipts.append(receipt)

        return receipts

    def _apply_action(
        self,
        farm: FarmDigitalTwin,
        action_type: str,
        zone_id: Optional[str],
        params: Dict[str, Any]
    ) -> str:
        """Executes actual state changes on targeted plot zones."""
        if not zone_id:
            return "SUCCESS_BROADCAST"

        zone = farm.get_zone(zone_id)
        if not zone:
            return f"FAILED_ZONE_NOT_FOUND_{zone_id}"

        if action_type in ("irrigate", "irrigate_zone"):
            volume_mm = params.get("volume_mm", 10.0)
            # 1mm irrigation ~ +1.5% soil moisture
            zone.soil_moisture_pct = min(92.0, round(zone.soil_moisture_pct + (volume_mm * 1.5), 1))
            zone.last_irrigated_timestamp = time.time()
            if zone.soil_moisture_pct >= 40.0 and zone.health_status == "water_stressed":
                zone.health_status = "healthy"
            return "SUCCESS_IRRIGATED"

        elif action_type in ("fertilize", "foliar_spray"):
            # Nitrogen fertilization boosts chlorophyll & NDVI
            zone.ndvi = min(0.95, round(zone.ndvi + 0.05, 2))
            if zone.health_status == "low_biomass":
                zone.health_status = "healthy"
            return "SUCCESS_FERTILIZED"

        elif action_type in ("fungicide_spray", "treat_pest"):
            zone.health_status = "healthy"
            return "SUCCESS_SPRAYED"

        return "SUCCESS_GENERIC"

    def verify_ledger_integrity(self) -> bool:
        """Validates that no audit receipts have been tampered with or modified."""
        if not self.audit_ledger:
            return True

        for i, receipt in enumerate(self.audit_ledger):
            # Check self-hash
            if receipt.entry_hash != receipt.calculate_hash():
                return False
            # Check chaining
            if i == 0:
                if receipt.prev_hash != self._genesis_hash:
                    return False
            else:
                if receipt.prev_hash != self.audit_ledger[i - 1].entry_hash:
                    return False

        return True
