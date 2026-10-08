import math

import pandas as pd

from .business_rules import (
    prioritize_inventory_exceptions,
    prioritize_reconciliation_exceptions,
)
from .engine import (
    find_low_stock_items,
    find_orphan_invoices,
    load_data,
    reconcile_orders_and_invoices,
)


def _json_safe_records(dataframe: pd.DataFrame) -> list[dict]:
    """
    Convert a Pandas DataFrame into JSON-safe records.

    Pandas represents missing values as NaN, but JSON APIs and
    Gemini require missing values to be represented as null.
    """
    records = dataframe.to_dict(orient="records")

    for record in records:
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                record[key] = None

    return records


def build_operations_report() -> dict:
    """
    Build a structured business operations report
    from orders, invoices, and inventory data.
    """

    orders, invoices, inventory = load_data()

    reconciliation = reconcile_orders_and_invoices(
        orders,
        invoices,
    )

    orphan_invoices = find_orphan_invoices(
        orders,
        invoices,
    )

    low_stock = find_low_stock_items(
        inventory,
    )

    financial_exceptions = (
        prioritize_reconciliation_exceptions(
            reconciliation
        )
    )

    inventory_exceptions = (
        prioritize_inventory_exceptions(
            low_stock
        )
    )

    return {
        "summary": {
            "orders_processed": len(orders),
            "invoices_processed": len(invoices),
            "inventory_records": len(inventory),
            "matched_orders": int(
                (
                    reconciliation[
                        "reconciliation_status"
                    ]
                    == "MATCHED"
                ).sum()
            ),
            "financial_exceptions": len(
                financial_exceptions
            ),
            "orphan_invoices": len(
                orphan_invoices
            ),
            "inventory_exceptions": len(
                inventory_exceptions
            ),
        },
        "financial_exceptions": _json_safe_records(
            financial_exceptions
        ),
        "orphan_invoices": _json_safe_records(
            orphan_invoices
        ),
        "inventory_exceptions": _json_safe_records(
            inventory_exceptions
        ),
    }


if __name__ == "__main__":
    report = build_operations_report()

    print("\nAI BUSINESS OPERATIONS REPORT")
    print("=" * 60)

    print("\nSUMMARY")
    print("-" * 60)

    for key, value in report["summary"].items():
        print(f"{key}: {value}")

    print("\nFINANCIAL EXCEPTIONS")
    print("-" * 60)

    for item in report["financial_exceptions"]:
        print(
            f"{item['order_id']} | "
            f"{item['reconciliation_status']} | "
            f"{item['priority']} | "
            f"{item['recommended_action']}"
        )

    print("\nORPHAN INVOICES")
    print("-" * 60)

    for item in report["orphan_invoices"]:
        print(
            f"{item['invoice_id']} | "
            f"Order: {item['order_id']} | "
            f"Amount: ${item['invoice_amount']:.2f}"
        )

    print("\nINVENTORY EXCEPTIONS")
    print("-" * 60)

    for item in report["inventory_exceptions"]:
        print(
            f"{item['sku']} | "
            f"{item['product_name']} | "
            f"{item['priority']} | "
            f"{item['recommended_action']}"
        )

    print("\n" + "=" * 60)

