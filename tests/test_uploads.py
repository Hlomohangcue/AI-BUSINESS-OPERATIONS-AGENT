import pandas as pd
import pytest

from src.reconciliation.report import build_operations_report
from src.reconciliation.uploads import validate_business_csv


def valid_orders():
    return pd.DataFrame({
        "order_id": ["ORD-1"],
        "customer": ["Customer A"],
        "sku": ["SKU-1"],
        "quantity": [2],
        "unit_price": [25.0],
    })


def valid_invoices():
    return pd.DataFrame({
        "invoice_id": ["INV-1"],
        "order_id": ["ORD-1"],
        "invoice_amount": [50.0],
        "status": ["Paid"],
    })


def valid_inventory():
    return pd.DataFrame({
        "sku": ["SKU-1"],
        "product_name": ["Mouse"],
        "stock_quantity": [25],
        "reorder_level": [10],
        "unit_cost": [12.0],
    })


def test_valid_orders_are_normalized_and_accepted():
    frame = valid_orders()
    frame.columns = [column.upper() for column in frame.columns]

    result = validate_business_csv(frame, "orders")

    assert list(result["order_id"]) == ["ORD-1"]
    assert result["quantity"].dtype == "int64"


def test_missing_required_column_is_rejected():
    frame = valid_orders().drop(columns=["customer"])

    with pytest.raises(ValueError, match="missing required columns"):
        validate_business_csv(frame, "orders")


def test_duplicate_order_ids_are_rejected():
    frame = pd.concat([valid_orders(), valid_orders()], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate identifiers"):
        validate_business_csv(frame, "orders")


def test_negative_unit_price_is_rejected():
    frame = valid_orders()
    frame.loc[0, "unit_price"] = -1

    with pytest.raises(ValueError, match="cannot contain negative"):
        validate_business_csv(frame, "orders")


def test_non_numeric_invoice_amount_is_rejected():
    frame = valid_invoices()
    frame["invoice_amount"] = ["unknown"]

    with pytest.raises(ValueError, match="must contain valid numbers"):
        validate_business_csv(frame, "invoices")


def test_multiple_invoices_per_order_are_rejected():
    frame = pd.concat([valid_invoices(), valid_invoices()], ignore_index=True)
    frame.loc[1, "invoice_id"] = "INV-2"

    with pytest.raises(ValueError, match="Multiple invoices"):
        validate_business_csv(frame, "invoices")


def test_custom_data_builds_report_without_changing_demo_data():
    orders = validate_business_csv(valid_orders(), "orders")
    invoices = validate_business_csv(valid_invoices(), "invoices")
    inventory = validate_business_csv(valid_inventory(), "inventory")

    report = build_operations_report(orders, invoices, inventory)

    assert report["summary"]["orders_processed"] == 1
    assert report["summary"]["invoices_processed"] == 1
    assert report["summary"]["matched_orders"] == 1
    assert report["summary"]["financial_exceptions"] == 0
    assert report["summary"]["inventory_exceptions"] == 0


def test_partial_custom_data_is_rejected():
    with pytest.raises(ValueError, match="must be supplied together"):
        build_operations_report(orders=valid_orders())
