"""Read XES event logs and return a validated DataFrame with metadata."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from core.data_contract import (
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)

if TYPE_CHECKING:
    import pandas as pd


class DatasetMetadata(TypedDict):
    """Metadata returned alongside a loaded event DataFrame."""

    file_name: str
    case_count: int
    event_count: int
    attributes: list[str]
    optional_attributes: list[str]


def load_xes(file_path: str | Path) -> tuple[pd.DataFrame, DatasetMetadata]:
    """Load and validate an XES file using PM4Py.

    Returns ``(event_df, metadata)``. The DataFrame retains all source
    attributes, converts ``time:timestamp`` to UTC datetimes, and is stably
    ordered by case and timestamp. Invalid timestamp values become ``NaT``;
    events sharing the same case and timestamp retain their source order.

    Metadata keys are ``file_name``, ``case_count``, ``event_count``,
    ``attributes``, and ``optional_attributes``.
    """
    if not isinstance(file_path, (str, Path)) or not str(file_path).strip():
        raise ValueError("Please provide a valid path to an XES file.")

    path = Path(file_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"XES file not found: {path}")
    if not path.is_file():
        raise ValueError(f"The XES path is not a file: {path}")
    if path.suffix.lower() != ".xes":
        raise ValueError(f"Unsupported file format for '{path.name}'; expected a .xes file.")

    try:
        import pandas as pd
        import pm4py
    except ImportError as exc:
        raise RuntimeError(
            "Loading XES requires Pandas and PM4Py. Install the project "
            "dependencies from requirements.txt in the active environment."
        ) from exc

    try:
        event_log = pm4py.read_xes(str(path))
        event_df = pm4py.convert_to_dataframe(event_log)
    except Exception as exc:
        raise ValueError(f"Could not read XES file '{path.name}': {exc}") from exc

    if not isinstance(event_df, pd.DataFrame):
        raise ValueError(
            f"PM4Py did not return a DataFrame for '{path.name}'."
        )

    optional_attributes = validate_event_dataframe(event_df)
    event_df = event_df.copy()
    event_df[TIMESTAMP_ATTRIBUTE] = pd.to_datetime(
        event_df[TIMESTAMP_ATTRIBUTE],
        errors="coerce",
        utc=True,
    )

    order_column = "__dataset_loader_event_order__"
    while order_column in event_df.columns:
        order_column = f"_{order_column}"
    event_df[order_column] = range(len(event_df))
    event_df = (
        event_df.sort_values(
            by=[CASE_ID_ATTRIBUTE, TIMESTAMP_ATTRIBUTE, order_column],
            kind="mergesort",
            na_position="last",
        )
        .drop(columns=order_column)
        .reset_index(drop=True)
    )

    metadata: DatasetMetadata = {
        "file_name": path.name,
        "case_count": int(event_df[CASE_ID_ATTRIBUTE].nunique()),
        "event_count": len(event_df),
        "attributes": [str(attribute) for attribute in event_df.columns],
        "optional_attributes": [
            attribute
            for attribute in OPTIONAL_ATTRIBUTES
            if attribute in optional_attributes
        ],
    }
    return event_df, metadata


__all__ = ["DatasetMetadata", "load_xes"]
