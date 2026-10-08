from datetime import datetime, timezone
from uuid import uuid4
from copy import deepcopy


# Temporary in-memory workflow store.
# This will later be replaced with persistent storage such as SQLite.
_workflow_actions: dict[str, dict] = {}


def create_replenishment_request(sku: str, reason: str) -> dict:
    """
    Create a replenishment request that requires human approval.

    This function does not place an order or modify inventory.
    It only creates a pending workflow action.
    """

    action_id = f"ACT-{uuid4().hex[:8].upper()}"

    action = {
        "action_id": action_id,
        "action": "REPLENISHMENT_REQUEST",
        "sku": sku,
        "reason": reason,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _workflow_actions[action_id] = action

    return deepcopy(action)


def propose_replenishment_request(sku: str, reason: str) -> dict:
    """
    Create an AI-generated replenishment proposal.

    The proposal always starts in PENDING_APPROVAL.
    The AI cannot approve or execute the action.
    """

    return create_replenishment_request(
        sku=sku,
        reason=reason,
    )
    

def approve_workflow_action(action_id: str, approver: str) -> dict:
    """
    Approve a pending workflow action.

    Approval must be performed explicitly by a human approver.
    """

    action = _workflow_actions.get(action_id)

    if action is None:
        return {
            "found": False,
            "action_id": action_id,
            "message": f"Workflow action {action_id} not found.",
        }

    if action["status"] != "PENDING_APPROVAL":
        return {
            "found": True,
            "action_id": action_id,
            "status": action["status"],
            "message": "Only pending actions can be approved.",
        }

    action["status"] = "APPROVED"
    action["approved_by"] = approver
    action["approved_at"] = datetime.now(timezone.utc).isoformat()

    return deepcopy(action)


def execute_workflow_action(action_id: str) -> dict:
    """
    Execute an approved workflow action.

    This is currently a simulation. It does not place a real
    purchase order or modify inventory.

    An action must be explicitly approved before execution.
    """

    action = _workflow_actions.get(action_id)

    if action is None:
        return {
            "found": False,
            "action_id": action_id,
            "message": f"Workflow action {action_id} not found.",
        }

    if action["status"] != "APPROVED":
        return {
            "found": True,
            "action_id": action_id,
            "status": action["status"],
            "message": "Only approved actions can be executed.",
        }

    action["status"] = "EXECUTED"
    action["executed_at"] = datetime.now(timezone.utc).isoformat()

    return deepcopy(action)