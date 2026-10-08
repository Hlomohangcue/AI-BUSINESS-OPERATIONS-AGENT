from src.workflows.actions import (
    approve_workflow_action,
    create_replenishment_request,
    execute_workflow_action,
    propose_replenishment_request,
)


def test_replenishment_request_starts_pending_approval():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    assert action["action"] == "REPLENISHMENT_REQUEST"
    assert action["sku"] == "SKU-004"
    assert action["reason"] == "Stock is below reorder level"
    assert action["status"] == "PENDING_APPROVAL"
    assert action["action_id"].startswith("ACT-")
    assert "created_at" in action
    

from src.workflows.actions import (
    approve_workflow_action,
    create_replenishment_request,
)


def test_pending_action_can_be_approved():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    approved = approve_workflow_action(
        action["action_id"],
        "Operations Manager",
    )

    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == "Operations Manager"
    assert "approved_at" in approved
    

def test_unapproved_action_cannot_execute():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    result = execute_workflow_action(action["action_id"])

    assert result["found"] is True
    assert result["status"] == "PENDING_APPROVAL"
    assert result["message"] == "Only approved actions can be executed."
    

def test_approved_action_can_execute():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    approved = approve_workflow_action(
        action["action_id"],
        "Operations Manager",
    )

    executed = execute_workflow_action(action["action_id"])

    assert approved["status"] == "APPROVED"
    assert executed["status"] == "EXECUTED"
    assert executed["action_id"] == action["action_id"]
    assert executed["approved_by"] == "Operations Manager"
    assert "executed_at" in executed
    
    
def test_executed_action_cannot_execute_again():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    approve_workflow_action(
        action["action_id"],
        "Operations Manager",
    )

    first_execution = execute_workflow_action(action["action_id"])

    second_execution = execute_workflow_action(action["action_id"])

    assert first_execution["status"] == "EXECUTED"
    assert second_execution["status"] == "EXECUTED"
    assert second_execution["message"] == "Only approved actions can be executed."  
    
    
def test_unknown_action_cannot_be_approved():
    result = approve_workflow_action(
        "ACT-UNKNOWN",
        "Operations Manager",
    )

    assert result["found"] is False
    assert result["action_id"] == "ACT-UNKNOWN"  
    
    
def test_unknown_action_cannot_be_executed():
    result = execute_workflow_action("ACT-UNKNOWN")

    assert result["found"] is False
    assert result["action_id"] == "ACT-UNKNOWN"
    
    
def test_approved_action_cannot_be_approved_again():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
    )

    first_approval = approve_workflow_action(
        action["action_id"],
        "Operations Manager",
    )

    second_approval = approve_workflow_action(
        action["action_id"],
        "Another Manager",
    )

    assert first_approval["status"] == "APPROVED"
    assert second_approval["status"] == "APPROVED"
    assert second_approval["message"] == "Only pending actions can be approved."
    

def test_ai_replenishment_proposal_requires_approval():
    proposal = propose_replenishment_request(
        "SKU-004",
        "AI detected stock below the configured reorder level.",
    )

    assert proposal["action"] == "REPLENISHMENT_REQUEST"
    assert proposal["sku"] == "SKU-004"
    assert proposal["status"] == "PENDING_APPROVAL"

    execution_attempt = execute_workflow_action(
        proposal["action_id"]
    )

    assert execution_attempt["status"] == "PENDING_APPROVAL"
    assert execution_attempt["message"] == "Only approved actions can be executed."