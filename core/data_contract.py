"""Shared XES event attribute names and DataFrame validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

CASE_ID_ATTRIBUTE = "case:concept:name"
ACTIVITY_ATTRIBUTE = "concept:name"
TIMESTAMP_ATTRIBUTE = "time:timestamp"

REQUIRED_ATTRIBUTES = (
    CASE_ID_ATTRIBUTE,
    ACTIVITY_ATTRIBUTE,
    TIMESTAMP_ATTRIBUTE,
)
OPTIONAL_ATTRIBUTES = (
    "lifecycle:transition",
    "org:resource",
)


def validate_event_dataframe(
    event_df: pd.DataFrame,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    """Validate required event columns and return optional columns that exist.

    Empty frames are rejected by default. Callers that need to render an empty
    result can explicitly pass ``allow_empty=True``.
    """
    if not hasattr(event_df, "columns") or not hasattr(event_df, "empty"):
        raise TypeError("event_df must be a Pandas DataFrame.")

    missing = [
        attribute
        for attribute in REQUIRED_ATTRIBUTES
        if attribute not in event_df.columns
    ]
    if missing:
        raise ValueError(
            "Event DataFrame is missing required XES attribute(s): "
            + ", ".join(missing)
        )
    if event_df.empty and not allow_empty:
        raise ValueError("Event DataFrame is empty.")

    return tuple(
        attribute
        for attribute in OPTIONAL_ATTRIBUTES
        if attribute in event_df.columns
    )


__all__ = [
    "ACTIVITY_ATTRIBUTE",
    "CASE_ID_ATTRIBUTE",
    "OPTIONAL_ATTRIBUTES",
    "REQUIRED_ATTRIBUTES",
    "TIMESTAMP_ATTRIBUTE",
    "validate_event_dataframe",
]
