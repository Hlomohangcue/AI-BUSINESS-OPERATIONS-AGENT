
"""Tests that agent tools use request-scoped uploaded datasets."""

import json

import pandas as pd

from src.agents.business_data_context import (
    set_current_business_data,
    reset_current_business_data,
)
from src.agents.business_operations_agent import (
    get_operations_report,
    investigate_order,
    investigate_invoice,
    investigate_inventory,
)


def make_uploaded_datasets():
    orders = pd.DataFrame(
        [
            {
                "order_id": "CUSTOM-ORDER-1",
                "customer": "Uploaded Customer",
                "sku": "CUSTOM-SKU-1",
                "quantity": 2,
                "unit_price": 15.0,
            },
        ]
    )

    invoices = pd.DataFrame(
        [
            {
                "invoice_id": "CUSTOM-INVOICE-1",
                "order_id": "CUSTOM-ORDER-1",
                "invoice_amount": 40.0,
                "status": "Pending",
            },
            {
                "invoice_id": "CUSTOM-ORPHAN-1",
                "order_id": "CUSTOM-MISSING-ORDER",
                "invoice_amount": 5.0,
                "status": "Pending",
            },
        ]
    )

    inventory = pd.DataFrame(
        [
            {
                "sku": "CUSTOM-SKU-1",
                "product_name": "Uploaded Product",
                "stock_quantity": 1,
                "reorder_level": 5,
                "unit_cost": 8.0,
            },
        ]
    )

    return orders, invoices, inventory


def test_operations_report_uses_uploaded_datasets():
    datasets = make_uploaded_datasets()
    token = set_current_business_data(*datasets)

    try:
        report = get_operations_report()
        report_text = json.dumps(report, default=str)

        assert "CUSTOM-ORDER-1" in report_text
        assert "CUSTOM-INVOICE-1" in report_text
        assert "CUSTOM-ORPHAN-1" in report_text
        assert "CUSTOM-SKU-1" in report_text
    finally:
        reset_current_business_data(token)

def test_order_investigation_uses_uploaded_datasets():
    datasets = make_uploaded_datasets()
    token = set_current_business_data(*datasets)

    try:
        result = investigate_order("CUSTOM-ORDER-1")

        assert result["found"] is True
        assert result["order_id"] == "CUSTOM-ORDER-1"
        assert result["invoice"]["invoice_id"] == "CUSTOM-INVOICE-1"
        assert result["reconciliation"]["status"] == "AMOUNT_MISMATCH"
        assert result["reconciliation"]["amount_difference"] == 10.0

        unknown = investigate_order("ORD-1004")
        assert unknown["found"] is False
    finally:
        reset_current_business_data(token)


def test_invoice_investigation_uses_uploaded_datasets():
    datasets = make_uploaded_datasets()
    token = set_current_business_data(*datasets)

    try:
        matched_invoice = investigate_invoice("CUSTOM-INVOICE-1")

        assert matched_invoice["found"] is True
        assert matched_invoice["order_match"]["found"] is True
        assert (
            matched_invoice["order_match"]["order_id"]
            == "CUSTOM-ORDER-1"
        )

        orphan_invoice = investigate_invoice("CUSTOM-ORPHAN-1")

        assert orphan_invoice["found"] is True
        assert orphan_invoice["order_match"]["found"] is False

        unknown = investigate_invoice("INV-005")
        assert unknown["found"] is False
    finally:
        reset_current_business_data(token)


def test_inventory_investigation_uses_uploaded_datasets():
    datasets = make_uploaded_datasets()
    token = set_current_business_data(*datasets)

    try:
        result = investigate_inventory("CUSTOM-SKU-1")

        assert result["found"] is True
        assert result["product"]["name"] == "Uploaded Product"
        assert result["product"]["stock_quantity"] == 1
        assert result["product"]["reorder_level"] == 5
        assert result["inventory"]["status"] == "LOW_STOCK"

        unknown = investigate_inventory("SKU-004")
        assert unknown["found"] is False
    finally:
        reset_current_business_data(token)
