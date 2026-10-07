import pandas as pd

from src.reconciliation.engine import (
    find_low_stock_items,
    find_orphan_invoices,
    reconcile_orders_and_invoices,
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