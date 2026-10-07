import pandas as pd

from .engine import (
    find_low_stock_items,
    find_orphan_invoices,
    load_data,
    reconcile_orders_and_invoices,
)


def main() -> None:
    print("=" * 60)
    print("AI BUSINESS OPERATIONS RECONCILIATION")
    print("=" * 60)

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

    matched = (
        reconciliation["reconciliation_status"] == "MATCHED"
    ).sum()

    amount_mismatches = (
        reconciliation["reconciliation_status"]
        == "AMOUNT_MISMATCH"
    ).sum()

    missing_invoices = (
        reconciliation["reconciliation_status"]
        == "MISSING_INVOICE"
    ).sum()

    print()
    print(f"Orders processed:       {len(orders)}")
    print(f"Invoices processed:     {len(invoices)}")
    print(f"Inventory records:      {len(inventory)}")
    print()
    print(f"Matched orders:         {matched}")
    print(f"Invoice mismatches:     {amount_mismatches}")
    print(f"Missing invoices:       {missing_invoices}")
    print(f"Orphan invoices:        {len(orphan_invoices)}")
    print(f"Low-stock products:     {len(low_stock)}")
    print()

    if (
        amount_mismatches
        or missing_invoices
        or len(orphan_invoices)
        or len(low_stock)
    ):
        print("Status: ACTION REQUIRED")
    else:
        print("Status: ALL CLEAR")

    print()
    
    print("\nRECONCILIATION EXCEPTIONS")
    print("-" * 60)

    exceptions = reconciliation[
        reconciliation["reconciliation_status"] != "MATCHED"
    ]

    if exceptions.empty:
        print("No reconciliation exceptions found.")
    else:
        for _, row in exceptions.iterrows():
            print(
                f"{row['order_id']} | "
                f"{row['reconciliation_status']} | "
                f"Expected: ${row['expected_amount']:.2f} | "
                f"Invoice: "
                f"${row['invoice_amount']:.2f}"
                if pd.notna(row["invoice_amount"])
                else
                f"{row['order_id']} | "
                f"{row['reconciliation_status']}"
            )

    if not orphan_invoices.empty:
        print("\nORPHAN INVOICES")
        print("-" * 60)

        for _, row in orphan_invoices.iterrows():
            print(
                f"{row['invoice_id']} | "
                f"Order: {row['order_id']} | "
                f"Amount: ${row['invoice_amount']:.2f}"
            )

    if not low_stock.empty:
        print("\nLOW STOCK")
        print("-" * 60)

        for _, row in low_stock.iterrows():
            print(
                f"{row['sku']} | "
                f"{row['product_name']} | "
                f"Stock: {row['stock_quantity']} | "
                f"Reorder level: {row['reorder_level']}"
            )
    
    print("=" * 60)


if __name__ == "__main__":
    main()