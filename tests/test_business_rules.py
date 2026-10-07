import pandas as pd

from src.reconciliation.business_rules import (
    prioritize_inventory_exceptions,
    prioritize_reconciliation_exceptions,
)


def test_prioritize_reconciliation_exceptions():
    reconciliation = pd.DataFrame(
        [
            ["ORD-001", "MATCHED"],
            ["ORD-002", "AMOUNT_MISMATCH"],
            ["ORD-003", "MISSING_INVOICE"],
        ],
        columns=[
            "order_id",
            "reconciliation_status",
        ],
    )

    result = prioritize_reconciliation_exceptions(
        reconciliation
    )

    assert len(result) == 2

    mismatch = result[
        result["order_id"] == "ORD-002"
    ].iloc[0]

    assert mismatch["priority"] == "HIGH"
    assert (
        mismatch["recommended_action"]
        == "Review invoice amount against order."
    )

    missing_invoice = result[
        result["order_id"] == "ORD-003"
    ].iloc[0]

    assert missing_invoice["priority"] == "HIGH"
    assert (
        missing_invoice["recommended_action"]
        == "Contact accounting team for missing invoice."
    )
    
def test_prioritize_inventory_exceptions():
    inventory = pd.DataFrame(
        [
            ["SKU-001", "Mouse", 0, 10],
            ["SKU-002", "Keyboard", 8, 10],
            ["SKU-003", "Cable", 20, 10],
        ],
        columns=[
            "sku",
            "product_name",
            "stock_quantity",
            "reorder_level",
        ],
    )

    result = prioritize_inventory_exceptions(
        inventory
    )

    critical_item = result[
        result["sku"] == "SKU-001"
    ].iloc[0]

    assert critical_item["priority"] == "CRITICAL"
    assert (
        critical_item["recommended_action"]
        == "Immediate replenishment required."
    )

    high_item = result[
        result["sku"] == "SKU-002"
    ].iloc[0]

    assert high_item["priority"] == "HIGH"

    normal_item = result[
        result["sku"] == "SKU-003"
    ].iloc[0]

    assert normal_item["priority"] == "MEDIUM"    