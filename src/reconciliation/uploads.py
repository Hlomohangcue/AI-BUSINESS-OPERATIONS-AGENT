"""Validation helpers for session-only business CSV uploads."""

import pandas as pd


REQUIRED_COLUMNS = {
    "orders": {
        "order_id", "customer", "sku", "quantity", "unit_price"
    },
    "invoices": {
        "invoice_id", "order_id", "invoice_amount", "status"
    },
    "inventory": {
        "sku", "product_name", "stock_quantity",
        "reorder_level", "unit_cost"
    },
}

UNIQUE_COLUMNS = {
    "orders": ["order_id"],
    "invoices": ["invoice_id"],
    "inventory": ["sku"],
}

NUMERIC_COLUMNS = {
    "orders": ["quantity", "unit_price"],
    "invoices": ["invoice_amount"],
    "inventory": [
        "stock_quantity", "reorder_level", "unit_cost"
    ],
}

NON_NEGATIVE_COLUMNS = {
    "orders": ["quantity", "unit_price"],
    "invoices": ["invoice_amount"],
    "inventory": [
        "stock_quantity", "reorder_level", "unit_cost"
    ],
}

INTEGER_COLUMNS = {
    "orders": ["quantity"],
    "inventory": ["stock_quantity", "reorder_level"],
}


def validate_business_csv(
    dataframe: pd.DataFrame,
    dataset: str,
) -> pd.DataFrame:
    """Validate and return a clean copy of an uploaded business dataset."""

    if dataset not in REQUIRED_COLUMNS:
        raise ValueError(f"Unsupported dataset type: {dataset}")

    if dataframe.empty:
        raise ValueError(f"The {dataset} CSV contains no data rows.")

    frame = dataframe.copy()
    frame.columns = [
        str(column).strip().lower() for column in frame.columns
    ]

    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("The CSV contains duplicate column names.")

    required = REQUIRED_COLUMNS[dataset]
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"The {dataset} CSV is missing required columns: "
            + ", ".join(missing)
        )

    # Normalize required text fields and reject missing/blank values.
    text_columns = required - set(NUMERIC_COLUMNS[dataset])
    for column in text_columns:
        frame[column] = frame[column].astype("string").str.strip()
        invalid = (
            frame[column].isna()
            | frame[column].eq("")
            | frame[column].str.lower().isin(
                ["nan", "none", "null", "<na>"]
            )
        )
        if invalid.any():
            raise ValueError(
                f"Column '{column}' contains missing or blank values."
            )

    # Convert numeric fields strictly; do not silently coerce bad values.
    for column in NUMERIC_COLUMNS[dataset]:
        try:
            frame[column] = pd.to_numeric(
                frame[column], errors="raise"
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Column '{column}' must contain valid numbers."
            ) from exc

        if frame[column].isna().any():
            raise ValueError(
                f"Column '{column}' contains missing numeric values."
            )

        if not frame[column].map(
            lambda value: pd.notna(value) and abs(float(value)) != float("inf")
        ).all():
            raise ValueError(
                f"Column '{column}' contains non-finite numeric values."
            )

        if (frame[column] < 0).any():
            raise ValueError(
                f"Column '{column}' cannot contain negative values."
            )

    for column in INTEGER_COLUMNS.get(dataset, []):
        if not frame[column].mod(1).eq(0).all():
            raise ValueError(
                f"Column '{column}' must contain whole numbers."
            )
        frame[column] = frame[column].astype("int64")

    for column in UNIQUE_COLUMNS[dataset]:
        if frame[column].duplicated().any():
            raise ValueError(
                f"Column '{column}' contains duplicate identifiers."
            )

    # Current reconciliation logic expects at most one invoice per order.
    if dataset == "invoices" and frame["order_id"].duplicated().any():
        raise ValueError(
            "Multiple invoices reference the same order. "
            "The current report supports one invoice per order."
        )

    return frame
