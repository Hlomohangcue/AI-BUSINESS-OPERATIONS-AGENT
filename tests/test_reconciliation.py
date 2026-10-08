import pandas as pd
import json
from src.reconciliation.report import build_operations_report

from src.reconciliation.engine import (
    find_low_stock_items,
    find_orphan_invoices,
    reconcile_orders_and_invoices,
    get_order_exception_details,
    get_invoice_exception_details,
    get_inventory_exception_details,
)


def test_reconcile_orders_and_invoices():
    orders = pd.DataFrame(
        [
            ["ORD-001", "Customer A", "SKU-001", 2, 25.00],
            ["ORD-002", "Customer B", "SKU-002", 1, 45.00],
            ["ORD-003", "Customer C", "SKU-003", 3, 15.00],
        ],
        columns=[
            "order_id",
            "customer",
            "sku",
            "quantity",
            "unit_price",
        ],
    )

    invoices = pd.DataFrame(
        [
            ["INV-001", "ORD-001", 50.00, "Paid"],
            ["INV-002", "ORD-002", 50.00, "Paid"],
        ],
        columns=[
            "invoice_id",
            "order_id",
            "invoice_amount",
            "status",
        ],
    )

    result = reconcile_orders_and_invoices(
        orders,
        invoices,
    )

    assert result.loc[
        result["order_id"] == "ORD-001",
        "reconciliation_status",
    ].iloc[0] == "MATCHED"

    assert result.loc[
        result["order_id"] == "ORD-002",
        "reconciliation_status",
    ].iloc[0] == "AMOUNT_MISMATCH"

    assert result.loc[
        result["order_id"] == "ORD-003",
        "reconciliation_status",
    ].iloc[0] == "MISSING_INVOICE"


def test_find_orphan_invoices():
    orders = pd.DataFrame(
        {"order_id": ["ORD-001", "ORD-002"]}
    )

    invoices = pd.DataFrame(
        {
            "invoice_id": ["INV-001", "INV-002"],
            "order_id": ["ORD-001", "ORD-999"],
            "invoice_amount": [50.00, 30.00],
            "status": ["Paid", "Paid"],
        }
    )

    result = find_orphan_invoices(
        orders,
        invoices,
    )

    assert len(result) == 1
    assert result.iloc[0]["invoice_id"] == "INV-002"
    assert result.iloc[0]["issue_type"] == "ORPHAN_INVOICE"


def test_find_low_stock_items():
    inventory = pd.DataFrame(
        {
            "sku": ["SKU-001", "SKU-002", "SKU-003"],
            "product_name": [
                "Mouse",
                "Keyboard",
                "Monitor",
            ],
            "stock_quantity": [25, 8, 3],
            "reorder_level": [10, 10, 5],
            "unit_cost": [12.00, 25.00, 80.00],
        }
    )

    result = find_low_stock_items(inventory)

    assert len(result) == 2
    assert set(result["sku"]) == {
        "SKU-002",
        "SKU-003",
    }
    
def test_ord_1004_amount_mismatch():
    result = get_order_exception_details("ORD-1004")

    assert result["found"] is True
    assert result["order_id"] == "ORD-1004"
    assert result["order"]["expected_amount"] == 100.0
    assert result["invoice"]["invoice_id"] == "INV-004"
    assert result["invoice"]["invoice_amount"] == 120.0
    assert result["reconciliation"]["status"] == "AMOUNT_MISMATCH"
    assert result["reconciliation"]["amount_difference"] == 20.0


def test_ord_1005_missing_invoice():
    result = get_order_exception_details("ORD-1005")

    assert result["found"] is True
    assert result["order_id"] == "ORD-1005"
    assert result["order"]["expected_amount"] == 50.0
    assert result["invoice"]["invoice_id"] is None
    assert result["invoice"]["invoice_amount"] is None
    assert result["reconciliation"]["status"] == "MISSING_INVOICE"
    assert result["reconciliation"]["amount_difference"] is None


def test_unknown_order_is_not_found():
    result = get_order_exception_details("ORD-9999")

    assert result["found"] is False
    assert result["order_id"] == "ORD-9999"
    assert "not found" in result["message"].lower()


def test_order_investigation_is_json_serializable():
    result = get_order_exception_details("ORD-1004")

    serialized = json.dumps(result, allow_nan=False)

    assert serialized
    assert '"order_id": "ORD-1004"' in serialized


def test_operations_report_is_json_serializable():
    report = build_operations_report()

    serialized = json.dumps(report, allow_nan=False)

    assert serialized
    assert report["summary"]["financial_exceptions"] == 2
    assert report["summary"]["inventory_exceptions"] == 2
    assert report["summary"]["orphan_invoices"] == 1
    
def test_invoice_investigation():
    result = get_invoice_exception_details("INV-004")

    assert result["found"] is True
    assert result["invoice_id"] == "INV-004"
    assert result["invoice"]["order_id"] == "ORD-1004"
    assert result["invoice"]["invoice_amount"] == 120.0
    assert result["invoice"]["status"] == "Paid"
    assert result["order_match"]["found"] is True


def test_orphan_invoice_investigation():
    result = get_invoice_exception_details("INV-005")

    assert result["found"] is True
    assert result["invoice_id"] == "INV-005"
    assert result["invoice"]["order_id"] == "ORD-9999"
    assert result["order_match"]["found"] is False


def test_unknown_invoice_is_not_found():
    result = get_invoice_exception_details("INV-999")

    assert result["found"] is False
    assert result["invoice_id"] == "INV-999"


def test_inventory_investigation():
    result = get_inventory_exception_details("SKU-004")

    assert result["found"] is True
    assert result["sku"] == "SKU-004"
    assert result["product"]["name"] == "Monitor"
    assert result["product"]["stock_quantity"] == 3
    assert result["product"]["reorder_level"] == 5
    assert result["inventory"]["status"] == "LOW_STOCK"
    assert result["inventory"]["below_reorder_level"] is True


def test_sufficient_inventory():
    result = get_inventory_exception_details("SKU-001")

    assert result["found"] is True
    assert result["inventory"]["status"] == "SUFFICIENT_STOCK"


def test_unknown_inventory_is_not_found():
    result = get_inventory_exception_details("SKU-999")

    assert result["found"] is False
    assert result["sku"] == "SKU-999"