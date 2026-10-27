"""
Cryptographic Audit Ledger & Action Dispatcher Endpoints (v1)
Provides immutable SHA-256 audit logs, chain verification, and manual actuator dispatch.
"""
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from backend.core.twin_state import FarmDigitalTwin
from backend.core.dispatcher import ActionDispatcher, AuditReceipt


router = APIRouter(prefix="/audit", tags=["Audit & Dispatch v1"])

# Global singleton dispatcher instance
_global_dispatcher = ActionDispatcher()


def get_farm_state() -> FarmDigitalTwin:
    from backend.main import farm_instance
    return farm_instance


def get_dispatcher() -> ActionDispatcher:
    return _global_dispatcher


class ManualDispatchRequest(BaseModel):
    action_type: str = Field(..., description="Type of actuator action: irrigate_zone, fertilize, fungicide_spray")
    zone_id: Optional[str] = Field(None, description="Target zone id (e.g. Z_0_0)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters like volume_mm")
    agent_name: str = Field("ManualOperator", description="Author or triggering agent")


@router.get("/ledger")
async def get_audit_ledger(
    limit: int = Query(50, ge=1, le=500, description="Max receipts to return"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    target_zone: Optional[str] = Query(None, description="Filter by target zone id"),
    dispatcher: ActionDispatcher = Depends(get_dispatcher)
) -> List[Dict[str, Any]]:
    """Retrieve chronologically ordered cryptographic receipts from the SHA-256 audit ledger."""
    filtered: List[AuditReceipt] = []

    for receipt in reversed(dispatcher.audit_ledger):
        if action_type and receipt.action_type.lower() != action_type.lower():
            continue
        if target_zone and receipt.target_zone != target_zone:
            continue
        filtered.append(receipt)
        if len(filtered) >= limit:
            break

    return [
        {
            "entry_index": r.entry_index,
            "timestamp": r.timestamp,
            "action_type": r.action_type,
            "target_zone": r.target_zone,
            "agent_name": r.agent_name,
            "parameters": r.parameters,
            "status": r.status,
            "prev_hash": r.prev_hash,
            "entry_hash": r.entry_hash
        }
        for r in filtered
    ]


@router.get("/verify")
async def verify_audit_ledger_integrity(
    dispatcher: ActionDispatcher = Depends(get_dispatcher)
) -> Dict[str, Any]:
    """Verify cryptographic hash chaining across all receipts in the audit ledger."""
    is_valid = dispatcher.verify_ledger_integrity()
    total_entries = len(dispatcher.audit_ledger)
    latest_hash = dispatcher.audit_ledger[-1].entry_hash if dispatcher.audit_ledger else "0" * 64

    return {
        "status": "valid" if is_valid else "corrupted",
        "is_valid": is_valid,
        "total_receipts": total_entries,
        "latest_hash": latest_hash,
        "algorithm": "SHA-256"
    }


@router.post("/dispatch")
async def dispatch_manual_action(
    payload: ManualDispatchRequest,
    farm: FarmDigitalTwin = Depends(get_farm_state),
    dispatcher: ActionDispatcher = Depends(get_dispatcher)
) -> Dict[str, Any]:
    """Enqueue and execute an actuator command, producing a newly minted audit receipt."""
    dispatcher.enqueue({
        "type": payload.action_type,
        "zone_id": payload.zone_id,
        "parameters": payload.parameters,
        "agent_name": payload.agent_name
    })

    receipts = dispatcher.execute_pending(farm)
    latest = receipts[-1] if receipts else None

    return {
        "status": "executed",
        "receipt": {
            "entry_index": latest.entry_index,
            "action_type": latest.action_type,
            "target_zone": latest.target_zone,
            "status": latest.status,
            "entry_hash": latest.entry_hash
        } if latest else None
    }
