import pytest

from src.workflows.actions import (
    approve_workflow_action,
    create_replenishment_request,
    execute_workflow_action,
    get_workflow_action_events,
    propose_replenishment_request,
)
from src.workflows.authorization import Actor, AuthorizationError, Role


OPERATOR = Actor(
    user_id="operator-1",
    organization_id="test-org",
    role=Role.OPERATOR,
)

APPROVER = Actor(
    user_id="approver-1",
    organization_id="test-org",
    role=Role.APPROVER,
)

OTHER_TENANT_ADMIN = Actor(
    user_id="admin-tenant-b",
    organization_id="tenant-b",
    role=Role.ADMINISTRATOR,
)


def test_replenishment_request_starts_pending_approval():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )

    assert action["action"] == "REPLENISHMENT_REQUEST"
    assert action["sku"] == "SKU-004"
    assert action["reason"] == "Stock is below reorder level"
    assert action["status"] == "PENDING_APPROVAL"
    assert action["action_id"].startswith("ACT-")
    assert action["organization_id"] == OPERATOR.organization_id
    assert action["created_at"]


def test_pending_action_can_be_approved():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )

    approved = approve_workflow_action(action["action_id"], APPROVER)

    assert approved["status"] == "APPROVED"
    assert approved["approved_by"] == APPROVER.user_id
    assert approved["approved_at"]


def test_unapproved_action_cannot_execute():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )

    result = execute_workflow_action(action["action_id"], APPROVER)

    assert result["found"] is True
    assert result["status"] == "PENDING_APPROVAL"
    assert result["message"] == "Only approved actions can be executed."


def test_approved_action_can_execute():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )

    approved = approve_workflow_action(action["action_id"], APPROVER)
    executed = execute_workflow_action(action["action_id"], APPROVER)

    assert approved["status"] == "APPROVED"
    assert executed["status"] == "EXECUTED"
    assert executed["action_id"] == action["action_id"]
    assert executed["approved_by"] == APPROVER.user_id
    assert executed["executed_at"]


def test_executed_action_cannot_execute_again():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )
    approve_workflow_action(action["action_id"], APPROVER)

    first_execution = execute_workflow_action(action["action_id"], APPROVER)
    second_execution = execute_workflow_action(action["action_id"], APPROVER)

    assert first_execution["status"] == "EXECUTED"
    assert second_execution["status"] == "EXECUTED"
    assert second_execution["message"] == (
        "Only approved actions can be executed."
    )


def test_unknown_action_cannot_be_approved():
    result = approve_workflow_action("ACT-UNKNOWN", APPROVER)

    assert result["found"] is False
    assert result["action_id"] == "ACT-UNKNOWN"


def test_unknown_action_cannot_be_executed():
    result = execute_workflow_action("ACT-UNKNOWN", APPROVER)

    assert result["found"] is False
    assert result["action_id"] == "ACT-UNKNOWN"


def test_approved_action_cannot_be_approved_again():
    action = create_replenishment_request(
        "SKU-004",
        "Stock is below reorder level",
        OPERATOR,
    )

    first_approval = approve_workflow_action(action["action_id"], APPROVER)
    second_approval = approve_workflow_action(action["action_id"], APPROVER)

    assert first_approval["status"] == "APPROVED"
    assert second_approval["status"] == "APPROVED"
    assert second_approval["message"] == "Only pending actions can be approved."


def test_ai_replenishment_proposal_requires_approval():
    proposal = propose_replenishment_request(
        "SKU-004",
        "AI detected stock below the configured reorder level.",
        OPERATOR,
    )

    assert proposal["action"] == "REPLENISHMENT_REQUEST"
    assert proposal["sku"] == "SKU-004"
    assert proposal["status"] == "PENDING_APPROVAL"

    execution_attempt = execute_workflow_action(
        proposal["action_id"],
        APPROVER,
    )

    assert execution_attempt["status"] == "PENDING_APPROVAL"
    assert execution_attempt["message"] == (
        "Only approved actions can be executed."
    )


def test_audit_trail_records_creation_approval_and_execution():
    action = create_replenishment_request(
        "SKU-004",
        "Audit trail test",
        OPERATOR,
    )

    approve_workflow_action(action["action_id"], APPROVER)
    execute_workflow_action(action["action_id"], APPROVER)

    events = get_workflow_action_events(action["action_id"], OPERATOR)

    assert [event["event_type"] for event in events] == [
        "ACTION_CREATED",
        "ACTION_APPROVED",
        "ACTION_EXECUTED",
    ]
    assert [event["actor"] for event in events] == [
        OPERATOR.user_id,
        APPROVER.user_id,
        APPROVER.user_id,
    ]
    assert all(event["occurred_at"] for event in events)


def test_failed_execution_does_not_create_success_event():
    action = create_replenishment_request(
        "SKU-004",
        "Failed execution audit test",
        OPERATOR,
    )

    result = execute_workflow_action(action["action_id"], APPROVER)
    events = get_workflow_action_events(action["action_id"], OPERATOR)

    assert result["status"] == "PENDING_APPROVAL"
    assert [event["event_type"] for event in events] == ["ACTION_CREATED"]


def test_failed_reapproval_does_not_create_duplicate_event():
    action = create_replenishment_request(
        "SKU-004",
        "Repeated approval audit test",
        OPERATOR,
    )

    approve_workflow_action(action["action_id"], APPROVER)
    approve_workflow_action(action["action_id"], APPROVER)

    events = get_workflow_action_events(action["action_id"], OPERATOR)

    assert [event["event_type"] for event in events] == [
        "ACTION_CREATED",
        "ACTION_APPROVED",
    ]
    assert events[1]["actor"] == APPROVER.user_id


def test_new_replenishment_action_has_creation_audit_event():
    action = create_replenishment_request(
        "SKU-004",
        "Verify creation audit event",
        OPERATOR,
    )

    events = get_workflow_action_events(action["action_id"], OPERATOR)

    assert len(events) == 1
    assert events[0]["event_type"] == "ACTION_CREATED"
    assert events[0]["actor"] == OPERATOR.user_id
    assert events[0]["occurred_at"] == action["created_at"]


def test_ai_proposal_has_creation_audit_event():
    proposal = propose_replenishment_request(
        "SKU-004",
        "AI audit regression test",
        OPERATOR,
    )

    events = get_workflow_action_events(proposal["action_id"], OPERATOR)

    assert proposal["status"] == "PENDING_APPROVAL"
    assert len(events) == 1
    assert events[0]["event_type"] == "ACTION_CREATED"
    assert events[0]["actor"] == OPERATOR.user_id


def test_viewer_cannot_create_replenishment_request():
    viewer = Actor("viewer-1", "test-org", Role.VIEWER)

    with pytest.raises(AuthorizationError):
        create_replenishment_request("SKU-004", "Test", viewer)


def test_operator_cannot_approve_or_execute():
    action = create_replenishment_request(
        "SKU-004",
        "Permission test",
        OPERATOR,
    )

    with pytest.raises(AuthorizationError):
        approve_workflow_action(action["action_id"], OPERATOR)

    with pytest.raises(AuthorizationError):
        execute_workflow_action(action["action_id"], OPERATOR)


def test_other_tenant_cannot_approve_or_execute_action():
    action = create_replenishment_request(
        "SKU-004",
        "Tenant isolation test",
        OPERATOR,
    )

    approval = approve_workflow_action(
        action["action_id"],
        OTHER_TENANT_ADMIN,
    )
    execution = execute_workflow_action(
        action["action_id"],
        OTHER_TENANT_ADMIN,
    )
    events = get_workflow_action_events(
        action["action_id"],
        OTHER_TENANT_ADMIN,
    )

    assert approval["found"] is False
    assert execution["found"] is False
    assert events == []
