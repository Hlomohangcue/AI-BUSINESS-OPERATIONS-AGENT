import pandas as pd


def prioritize_reconciliation_exceptions(
    reconciliation: pd.DataFrame,
) -> pd.DataFrame:
    """
    Assign business priority and recommended actions
    to reconciliation exceptions.
    """
    exceptions = reconciliation[
        reconciliation["reconciliation_status"] != "MATCHED"
    ].copy()

    def determine_priority(status: str) -> str:
        if status == "AMOUNT_MISMATCH":
            return "HIGH"

        if status == "MISSING_INVOICE":
            return "HIGH"

        return "MEDIUM"

    def determine_action(status: str) -> str:
        if status == "AMOUNT_MISMATCH":
            return "Review invoice amount against order."

        if status == "MISSING_INVOICE":
            return "Contact accounting team for missing invoice."

        return "Review exception."

    exceptions["priority"] = exceptions[
        "reconciliation_status"
    ].apply(determine_priority)

    exceptions["recommended_action"] = exceptions[
        "reconciliation_status"
    ].apply(determine_action)

    return exceptions

def prioritize_inventory_exceptions(
    low_stock: pd.DataFrame,
) -> pd.DataFrame:
    """
    Assign business priority and recommended actions
    to low-stock inventory items.
    """
    exceptions = low_stock.copy()

    def determine_priority(row: pd.Series) -> str:
        stock = row["stock_quantity"]
        reorder_level = row["reorder_level"]

        if stock == 0:
            return "CRITICAL"

        if stock < reorder_level:
            return "HIGH"

        return "MEDIUM"

    def determine_action(row: pd.Series) -> str:
        stock = row["stock_quantity"]

        if stock == 0:
            return "Immediate replenishment required."

        return "Review stock levels and consider replenishment."

    exceptions["priority"] = exceptions.apply(
        determine_priority,
        axis=1,
    )

    exceptions["recommended_action"] = exceptions.apply(
        determine_action,
        axis=1,
    )

    return exceptions