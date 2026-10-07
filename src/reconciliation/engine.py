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