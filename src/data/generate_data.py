from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).parent


def generate_orders() -> None:
    orders = pd.DataFrame(
        [
            ["ORD-1001", "Customer A", "SKU-001", 2, 25.00],
            ["ORD-1002", "Customer B", "SKU-002", 1, 45.00],
            ["ORD-1003", "Customer C", "SKU-003", 3, 15.00],
            ["ORD-1004", "Customer D", "SKU-004", 1, 100.00],
            ["ORD-1005", "Customer E", "SKU-005", 4, 12.50],
        ],
        columns=[
            "order_id",
            "customer",
            "sku",
            "quantity",
            "unit_price",
        ],
    )

    orders.to_csv(DATA_DIR / "orders.csv", index=False)


def generate_invoices() -> None:
    invoices = pd.DataFrame(
        [
            ["INV-001", "ORD-1001", 50.00, "Paid"],
            ["INV-002", "ORD-1002", 45.00, "Paid"],
            ["INV-003", "ORD-1003", 45.00, "Paid"],
            ["INV-004", "ORD-1004", 120.00, "Paid"],
            ["INV-005", "ORD-9999", 30.00, "Paid"],
        ],
        columns=[
            "invoice_id",
            "order_id",
            "invoice_amount",
            "status",
        ],
    )

    invoices.to_csv(DATA_DIR / "invoices.csv", index=False)


def generate_inventory() -> None:
    inventory = pd.DataFrame(
        [
            ["SKU-001", "Wireless Mouse", 25, 10, 12.00],
            ["SKU-002", "Keyboard", 8, 10, 25.00],
            ["SKU-003", "USB Cable", 50, 20, 5.00],
            ["SKU-004", "Monitor", 3, 5, 80.00],
            ["SKU-005", "Laptop Stand", 30, 10, 20.00],
        ],
        columns=[
            "sku",
            "product_name",
            "stock_quantity",
            "reorder_level",
            "unit_cost",
        ],
    )

    inventory.to_csv(DATA_DIR / "inventory.csv", index=False)


if __name__ == "__main__":
    generate_orders()
    generate_invoices()
    generate_inventory()

    print("Business sample data generated successfully.")