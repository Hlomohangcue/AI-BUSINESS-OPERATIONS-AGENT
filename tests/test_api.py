import asyncio
import io
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import FormData, UploadFile

from src.api.main import app

from types import SimpleNamespace

from src.api import main as api_main
from src.agents.business_data_context import get_current_business_data


TOKENS = {
    "viewer-token": {
        "user_id": "viewer-1",
        "organization_id": "test-org",
        "role": "viewer",
    },
    "operator-token": {
        "user_id": "operator-1",
        "organization_id": "test-org",
        "role": "operator",
    },
    "approver-token": {
        "user_id": "approver-1",
        "organization_id": "test-org",
        "role": "approver",
    },
    "administrator-token": {
        "user_id": "administrator-1",
        "organization_id": "test-org",
        "role": "administrator",
    },
    "other-tenant-token": {
        "user_id": "admin-tenant-b",
        "organization_id": "tenant-b",
        "role": "administrator",
    },
}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "BUSINESS_OPERATIONS_API_TOKENS_JSON",
        json.dumps(TOKENS),
    )
    with TestClient(app) as test_client:
        yield test_client


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_action(client):
    response = client.post(
        "/workflow/replenishment",
        headers=auth("operator-token"),
        json={
            "sku": "SKU-004",
            "reason": "API security regression test",
        },
    )
    assert response.status_code == 201
    return response.json()["action"]


def test_workflow_endpoints_reject_missing_or_invalid_tokens(client):
    missing = client.get("/workflow/actions/ACT-UNKNOWN")
    invalid = client.get(
        "/workflow/actions/ACT-UNKNOWN",
        headers=auth("invalid-token"),
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401


def test_authentication_fails_closed_when_token_registry_is_missing(
    client,
    monkeypatch,
):
    monkeypatch.delenv("BUSINESS_OPERATIONS_API_TOKENS_JSON")

    response = client.get(
        "/workflow/actions/ACT-UNKNOWN",
        headers=auth("operator-token"),
    )

    assert response.status_code == 503


def test_authentication_fails_closed_when_token_registry_is_invalid(
    client,
    monkeypatch,
):
    monkeypatch.setenv("BUSINESS_OPERATIONS_API_TOKENS_JSON", "not-json")

    response = client.get(
        "/workflow/actions/ACT-UNKNOWN",
        headers=auth("operator-token"),
    )

    assert response.status_code == 503


def test_proposal_identity_comes_from_authenticated_actor(client):
    response = client.post(
        "/workflow/replenishment",
        headers=auth("operator-token"),
        json={
            "sku": "SKU-004",
            "reason": "Identity spoofing regression test",
            "user_id": "attacker",
            "organization_id": "tenant-b",
            "role": "administrator",
        },
    )
    assert response.status_code == 201

    action = response.json()["action"]
    events_response = client.get(
        f"/workflow/actions/{action['action_id']}/events",
        headers=auth("operator-token"),
    )

    assert action["organization_id"] == "test-org"
    assert events_response.status_code == 200
    assert events_response.json()["events"][0]["actor"] == "operator-1"


def test_viewer_cannot_create_replenishment_request(client):
    response = client.post(
        "/workflow/replenishment",
        headers=auth("viewer-token"),
        json={"sku": "SKU-004", "reason": "Viewer permission test"},
    )

    assert response.status_code == 403


def test_operator_cannot_approve_or_execute_actions(client):
    action = create_action(client)
    action_id = action["action_id"]

    approval = client.post(
        f"/workflow/actions/{action_id}/approve",
        headers=auth("operator-token"),
    )
    execution = client.post(
        f"/workflow/actions/{action_id}/execute",
        headers=auth("operator-token"),
    )

    assert approval.status_code == 403
    assert execution.status_code == 403


def test_action_cannot_execute_before_approval(client):
    action = create_action(client)

    response = client.post(
        f"/workflow/actions/{action['action_id']}/execute",
        headers=auth("approver-token"),
    )

    assert response.status_code == 409
    assert "Only approved actions can be executed." in response.json()["detail"]

    events_response = client.get(
        f"/workflow/actions/{action['action_id']}/events",
        headers=auth("operator-token"),
    )
    assert events_response.status_code == 200
    assert [
        event["event_type"]
        for event in events_response.json()["events"]
    ] == ["ACTION_CREATED"]


def test_approver_can_approve_and_execute_action(client):
    action = create_action(client)
    action_id = action["action_id"]

    approval = client.post(
        f"/workflow/actions/{action_id}/approve",
        headers=auth("approver-token"),
    )
    assert approval.status_code == 200
    assert approval.json()["action"]["status"] == "APPROVED"

    execution = client.post(
        f"/workflow/actions/{action_id}/execute",
        headers=auth("approver-token"),
    )
    assert execution.status_code == 200
    assert execution.json()["action"]["status"] == "EXECUTED"
    assert "no external purchase was placed" in execution.json()["note"]

    events_response = client.get(
        f"/workflow/actions/{action_id}/events",
        headers=auth("operator-token"),
    )
    assert events_response.status_code == 200
    assert [
        event["event_type"]
        for event in events_response.json()["events"]
    ] == [
        "ACTION_CREATED",
        "ACTION_APPROVED",
        "ACTION_EXECUTED",
    ]


def test_proposer_cannot_approve_own_action_through_api(client):
    response = client.post(
        "/workflow/replenishment",
        headers=auth("administrator-token"),
        json={
            "sku": "SKU-004",
            "reason": "API separation of duties test",
        },
    )
    assert response.status_code == 201
    action_id = response.json()["action"]["action_id"]

    approval = client.post(
        f"/workflow/actions/{action_id}/approve",
        headers=auth("administrator-token"),
    )

    assert approval.status_code == 409
    assert approval.json()["detail"] == (
        "The proposer cannot approve their own action."
    )


def test_other_organization_cannot_access_action(client):
    action = create_action(client)

    response = client.get(
        f"/workflow/actions/{action['action_id']}",
        headers=auth("other-tenant-token"),
    )

    assert response.status_code == 404


def test_agent_chat_rejects_partial_csv_upload(client):
    response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Check my operations report"},
        files={
            "orders_file": (
                "orders.csv",
                b"order_id,customer,sku,quantity,unit_price\n"
                b"ORD-1,Customer A,SKU-1,2,10\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 422
    assert "Upload orders, invoices, and inventory CSV files together" in (
        response.json()["detail"]
    )


def test_multipart_form_is_closed_after_validation_failure(
    client,
    monkeypatch,
):
    close_calls = []
    original_close = FormData.close

    async def tracked_close(form):
        close_calls.append(True)
        await original_close(form)

    monkeypatch.setattr(FormData, "close", tracked_close)

    response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Check my operations report"},
        files={
            "orders_file": (
                "orders.csv",
                b"order_id,customer,sku,quantity,unit_price\n"
                b"ORD-1,Customer A,SKU-1,2,10\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 422
    assert close_calls == [True]


def test_csv_upload_at_size_limit_is_accepted(client, monkeypatch):
    async def fake_run_async(**kwargs):
        yield SimpleNamespace(
            is_final_response=lambda: True,
            content=SimpleNamespace(
                parts=[SimpleNamespace(text="Boundary upload received.")]
            ),
        )

    monkeypatch.setattr(api_main.agent_runner, "run_async", fake_run_async)
    max_size = 256
    orders_prefix = (
        b"order_id,customer,sku,quantity,unit_price\n"
        b"BOUNDARY-ORDER,"
    )
    orders_suffix = b",BOUNDARY-SKU,1,10\n"
    orders_csv = (
        orders_prefix
        + b"A" * (max_size - len(orders_prefix) - len(orders_suffix))
        + orders_suffix
    )
    assert len(orders_csv) == max_size
    monkeypatch.setattr(api_main, "MAX_CSV_UPLOAD_BYTES", max_size)

    response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Check the boundary upload."},
        files={
            "orders_file": ("orders.csv", orders_csv, "text/csv"),
            "invoices_file": (
                "invoices.csv",
                b"invoice_id,order_id,invoice_amount,status\n"
                b"BOUNDARY-INVOICE,BOUNDARY-ORDER,10,Paid\n",
                "text/csv",
            ),
            "inventory_file": (
                "inventory.csv",
                b"sku,product_name,stock_quantity,reorder_level,unit_cost\n"
                b"BOUNDARY-SKU,Boundary item,5,5,2\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200


def test_csv_upload_over_size_limit_is_rejected(client, monkeypatch):
    max_size = 256
    monkeypatch.setattr(api_main, "MAX_CSV_UPLOAD_BYTES", max_size)
    read_calls = []
    original_read = UploadFile.read

    async def tracked_read(upload, size=-1):
        read_calls.append(size)
        return await original_read(upload, size)

    monkeypatch.setattr(UploadFile, "read", tracked_read)
    orders_csv = (
        b"order_id,customer,sku,quantity,unit_price\n"
        + b"ORD-1,"
        + b"A" * max_size
        + b",SKU-1,1,10\n"
    )

    response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Check the oversized upload."},
        files={
            "orders_file": ("orders.csv", orders_csv, "text/csv"),
            "invoices_file": (
                "invoices.csv",
                b"invoice_id,order_id,invoice_amount,status\n"
                b"INV-1,ORD-1,10,Paid\n",
                "text/csv",
            ),
            "inventory_file": (
                "inventory.csv",
                b"sku,product_name,stock_quantity,reorder_level,unit_cost\n"
                b"SKU-1,Item,5,5,2\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 413
    assert read_calls == []


def test_unknown_upload_size_is_read_only_to_the_limit_plus_one(
    monkeypatch,
):
    max_size = 32
    monkeypatch.setattr(api_main, "MAX_CSV_UPLOAD_BYTES", max_size)
    upload = UploadFile(
        file=io.BytesIO(b"x" * (max_size + 20)),
        size=None,
        filename="orders.csv",
    )
    read_sizes = []
    original_read = UploadFile.read

    async def tracked_read(file, size=-1):
        read_sizes.append(size)
        return await original_read(file, size)

    monkeypatch.setattr(UploadFile, "read", tracked_read)

    with pytest.raises(HTTPException) as error:
        asyncio.run(api_main._read_csv_upload(upload, "orders_file"))

    assert error.value.status_code == 413
    assert read_sizes == [max_size + 1]


def test_malformed_csv_upload_is_rejected(client):
    response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Check malformed uploaded data."},
        files={
            "orders_file": (
                "orders.csv",
                b"unexpected,columns\nvalue,here\n",
                "text/csv",
            ),
            "invoices_file": (
                "invoices.csv",
                b"invoice_id,order_id,invoice_amount,status\n"
                b"INV-1,ORD-1,10,Paid\n",
                "text/csv",
            ),
            "inventory_file": (
                "inventory.csv",
                b"sku,product_name,stock_quantity,reorder_level,unit_cost\n"
                b"SKU-1,Item,5,5,2\n",
                "text/csv",
            ),
        },
    )

    assert response.status_code == 422
    assert "could not be parsed or failed CSV validation" in (
        response.json()["detail"]
    )


def test_agent_chat_uses_uploaded_datasets_and_resets_context(
    client,
    monkeypatch,
):
    observed_datasets = []

    async def fake_run_async(**kwargs):
        datasets = get_current_business_data()

        if datasets is None:
            observed_datasets.append(None)
        else:
            orders, invoices, inventory = datasets
            observed_datasets.append(
                {
                    "order_ids": orders["order_id"].tolist(),
                    "invoice_ids": invoices["invoice_id"].tolist(),
                    "skus": inventory["sku"].tolist(),
                }
            )

        yield SimpleNamespace(
            is_final_response=lambda: True,
            content=SimpleNamespace(
                parts=[SimpleNamespace(text="Test response received.")]
            ),
        )

    monkeypatch.setattr(
        api_main.agent_runner,
        "run_async",
        fake_run_async,
    )

    upload_response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        data={"message": "Review the uploaded business data."},
        files={
            "orders_file": (
                "orders.csv",
                (
                    b"order_id,customer,sku,quantity,unit_price\n"
                    b"CUSTOM-ORDER-1,Test Customer,CUSTOM-SKU-1,2,15\n"
                ),
                "text/csv",
            ),
            "invoices_file": (
                "invoices.csv",
                (
                    b"invoice_id,order_id,invoice_amount,status\n"
                    b"CUSTOM-INVOICE-1,CUSTOM-ORDER-1,30,Paid\n"
                ),
                "text/csv",
            ),
            "inventory_file": (
                "inventory.csv",
                (
                    b"sku,product_name,stock_quantity,reorder_level,unit_cost\n"
                    b"CUSTOM-SKU-1,Test Product,20,5,8\n"
                ),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    assert observed_datasets[0] == {
        "order_ids": ["CUSTOM-ORDER-1"],
        "invoice_ids": ["CUSTOM-INVOICE-1"],
        "skus": ["CUSTOM-SKU-1"],
    }

    # A subsequent request without uploads must not inherit prior data.
    demo_response = client.post(
        "/agent/chat",
        headers=auth("operator-token"),
        json={"message": "Review the demonstration data."},
    )

    assert demo_response.status_code == 200
    assert observed_datasets[1] is None
    assert get_current_business_data() is None
