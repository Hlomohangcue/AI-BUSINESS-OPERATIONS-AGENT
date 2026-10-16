"""Request-scoped business datasets for agent tool execution."""

from contextvars import ContextVar, Token

import pandas as pd


BusinessDatasets = tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]

_current_business_datasets: ContextVar[
    BusinessDatasets | None
] = ContextVar(
    "current_business_operations_datasets",
    default=None,
)


def set_current_business_data(
    orders: pd.DataFrame,
    invoices: pd.DataFrame,
    inventory: pd.DataFrame,
) -> Token:
    """Set validated datasets for the current request context."""
    if not all(
        isinstance(frame, pd.DataFrame)
        for frame in (orders, invoices, inventory)
    ):
        raise TypeError("All three business datasets must be DataFrames.")

    # Copy the frames so callers cannot change the context by
    # subsequently mutating their original DataFrames.
    datasets = (
        orders.copy(deep=True),
        invoices.copy(deep=True),
        inventory.copy(deep=True),
    )

    return _current_business_datasets.set(datasets)


def get_current_business_data() -> BusinessDatasets | None:
    """Return datasets for this request, or None for demo-data mode."""
    return _current_business_datasets.get()


def reset_current_business_data(token: Token) -> None:
    """Restore the previous context after the request finishes."""
    _current_business_datasets.reset(token)
