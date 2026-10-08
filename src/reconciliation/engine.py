from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load orders, invoices, and inventory data."""

    orders = pd.read_csv(DATA_DIR / "orders.csv")
    invoices = pd.read_csv(DATA_DIR / "invoices.csv")
    inventory = pd.read_csv(DATA_DIR / "inventory.csv")

    return orders, invoices, inventory


def reconcile_orders_and_invoices(
    orders: pd.DataFrame,
    invoices: pd.DataFrame,
) -> pd.DataFrame:
    """Compare orders against invoices and identify reconciliation issues."""

    orders = orders.copy()
    invoices = invoices.copy()

    # Calculate what each order should have been invoiced for.
    orders["expected_amount"] = (
        orders["quantity"] * orders["unit_price"]
    )

    # Match invoices to orders.
    reconciliation = orders.merge(
        invoices,
        on="order_id",
        how="left",
        indicator=True,
    )

    # Calculate the difference where an invoice exists.
    reconciliation["amount_difference"] = (
        reconciliation["invoice_amount"]
        - reconciliation["expected_amount"]
    )

    # Determine the reconciliation status.
    def determine_status(row: pd.Series) -> str:
        if row["_merge"] == "left_only":
            return "MISSING_INVOICE"

        if abs(row["amount_difference"]) > 0.01:
            return "AMOUNT_MISMATCH"

        return "MATCHED"

    reconciliation["reconciliation_status"] = (
        reconciliation.apply(determine_status, axis=1)
    )

    return reconciliation


def find_orphan_invoices(
    orders: pd.DataFrame,
    invoices: pd.DataFrame,
) -> pd.DataFrame:
    """Find invoices that reference orders that do not exist."""

    orphan_invoices = invoices[
        ~invoices["order_id"].isin(orders["order_id"])
    ].copy()

    orphan_invoices["issue_type"] = "ORPHAN_INVOICE"

    return orphan_invoices


def find_low_stock_items(
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    """Find products whose stock is at or below the reorder level."""

    low_stock = inventory[
        inventory["stock_quantity"] <= inventory["reorder_level"]
    ].copy()

    low_stock["issue_type"] = "LOW_STOCK"

    return low_stock

def get_order_exception_details(order_id: str) -> dict:
    """
    Retrieve verified reconciliation details for a specific order.

    This function performs deterministic lookup and reconciliation.
    The AI agent is responsible only for explaining the returned data.
    """

    orders, invoices, _ = load_data()

    reconciliation = reconcile_orders_and_invoices(
        orders,
        invoices,
    )

    matching_records = reconciliation[
        reconciliation["order_id"] == order_id
    ]

    if matching_records.empty:
        return {
            "found": False,
            "order_id": order_id,
            "message": "Order not found in the verified business data.",
        }

    record = matching_records.iloc[0]

    return {
        "found": True,
        "order_id": order_id,
        "order": {
            "customer": str(record["customer"]),
            "sku": str(record["sku"]),
            "quantity": int(record["quantity"]),
            "unit_price": float(record["unit_price"]),
            "expected_amount": float(record["expected_amount"]),
        },
        "invoice": {
            "invoice_id": (
                str(record["invoice_id"])
                if pd.notna(record["invoice_id"])
                else None
            ),
            "invoice_amount": (
                float(record["invoice_amount"])
                if pd.notna(record["invoice_amount"])
                else None
            ),
            "status": (
                str(record["status"])
                if pd.notna(record["status"])
                else None
            ),
        },
        "reconciliation": {
            "status": str(record["reconciliation_status"]),
            "amount_difference": (
                float(record["amount_difference"])
                if pd.notna(record["amount_difference"])
                else None
            ),
        },
    }
    
def get_invoice_exception_details(invoice_id: str) -> dict:
    """
    Investigate a specific invoice using verified deterministic data.

    Returns invoice details and whether the invoice can be matched
    to a verified order.
    """

    orders, invoices, _ = load_data()

    invoice_matches = invoices[invoices["invoice_id"] == invoice_id]

    if invoice_matches.empty:
        return {
            "found": False,
            "invoice_id": invoice_id,
            "message": f"Invoice {invoice_id} not found.",
        }

    invoice = invoice_matches.iloc[0]

    order_id = str(invoice["order_id"])

    matching_orders = orders[orders["order_id"] == order_id]

    return {
        "found": True,
        "invoice_id": invoice_id,
        "invoice": {
            "order_id": order_id,
            "invoice_amount": float(invoice["invoice_amount"]),
            "status": str(invoice["status"]),
        },
        "order_match": {
            "found": not matching_orders.empty,
            "order_id": order_id,
        },
    }
    
def get_inventory_exception_details(sku: str) -> dict:
    """
    Investigate a specific inventory item using verified deterministic data.
    """

    _, _, inventory = load_data()

    inventory_matches = inventory[inventory["sku"] == sku]

    if inventory_matches.empty:
        return {
            "found": False,
            "sku": sku,
            "message": f"Inventory item {sku} not found.",
        }

    item = inventory_matches.iloc[0]

    stock_quantity = int(item["stock_quantity"])
    reorder_level = int(item["reorder_level"])

    if stock_quantity == 0:
        inventory_status = "OUT_OF_STOCK"
    elif stock_quantity < reorder_level:
        inventory_status = "LOW_STOCK"
    else:
        inventory_status = "SUFFICIENT_STOCK"

    return {
        "found": True,
        "sku": sku,
        "product": {
            "name": str(item["product_name"]),
            "stock_quantity": stock_quantity,
            "reorder_level": reorder_level,
            "unit_cost": float(item["unit_cost"]),
        },
        "inventory": {
            "status": inventory_status,
            "below_reorder_level": stock_quantity < reorder_level,
        },
    }