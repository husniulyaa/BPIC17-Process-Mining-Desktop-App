"""Logika pengolahan data case & timeline untuk Case Explorer (F07).

Modul ini sengaja dipisahkan dari PySide6 agar pemrosesan data dan pengujian
dapat berjalan independen dari lapisan GUI sesuai prinsip TEAM_BASELINE.md.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    REQUIRED_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)

LIFECYCLE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[0]  # "lifecycle:transition"
RESOURCE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[1]  # "org:resource"
SECONDS_PER_DAY = 86400.0


def _parse_timestamps_utc(series: pd.Series) -> pd.Series:
    """Konversi kolom timestamp ke datetime UTC tanpa memodifikasi sumber."""
    try:
        return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce", utc=True)


def format_timestamp(value: Any) -> str | None:
    """Format nilai timestamp menjadi ISO-8601 string atau None jika NaT."""
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def format_duration_seconds(seconds: float | None) -> str:
    """Format durasi detik menjadi representasi ringkas (mis. '2d 04:15:00')."""
    if seconds is None or pd.isna(seconds):
        return "—"
    total_seconds = max(0.0, float(seconds))
    days, rem = divmod(int(total_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _clean_value(value: Any) -> Any:
    """Konversi nilai sel DataFrame agar aman diserialisasi/ditampilkan."""
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def build_case_summaries(event_df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Bangun daftar ringkasan per case secara terurut dan tervektorisasi.

    Satu elemen dikembalikan per case unik. Case yang memiliki timestamp tidak
    valid (``NaT``) ditandai ``has_invalid_timestamps=True`` dan memiliki
    ``duration_seconds=None`` agar tidak menghasilkan durasi yang keliru.
    """
    if event_df is None:
        return []

    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return []

    df = event_df[list(REQUIRED_ATTRIBUTES)].copy()
    df = df.loc[df[CASE_ID_ATTRIBUTE].notna()].copy()
    if df.empty:
        return []

    df["_case_id"] = df[CASE_ID_ATTRIBUTE].astype(str)
    df["_activity"] = df[ACTIVITY_ATTRIBUTE].where(
        df[ACTIVITY_ATTRIBUTE].notna(), "(missing)"
    ).astype(str)
    df["_ts"] = _parse_timestamps_utc(df[TIMESTAMP_ATTRIBUTE])
    df["_orig_order"] = range(len(df))

    df = df.sort_values(
        by=["_case_id", "_ts", "_orig_order"],
        kind="mergesort",
        na_position="last",
    )

    grouped = df.groupby("_case_id", sort=True)
    agg = grouped.agg(
        event_count=("_activity", "size"),
        unique_activities=("_activity", "nunique"),
        first_activity=("_activity", "first"),
        last_activity=("_activity", "last"),
        start_time=("_ts", "min"),
        end_time=("_ts", "max"),
        valid_ts_count=("_ts", "count"),
    )

    summaries: list[dict[str, Any]] = []
    for case_id, row in agg.iterrows():
        event_count = int(row["event_count"])
        has_invalid_ts = int(row["valid_ts_count"]) < event_count

        if has_invalid_ts or pd.isna(row["start_time"]) or pd.isna(row["end_time"]):
            start_iso = None if has_invalid_ts else format_timestamp(row["start_time"])
            end_iso = None if has_invalid_ts else format_timestamp(row["end_time"])
            duration_seconds: float | None = None
            duration_days: float | None = None
        else:
            start_iso = format_timestamp(row["start_time"])
            end_iso = format_timestamp(row["end_time"])
            duration_seconds = float(
                (row["end_time"] - row["start_time"]).total_seconds()
            )
            duration_days = duration_seconds / SECONDS_PER_DAY

        summaries.append(
            {
                "case_id": str(case_id),
                "event_count": event_count,
                "unique_activities": int(row["unique_activities"]),
                "start_time": start_iso,
                "end_time": end_iso,
                "duration_seconds": duration_seconds,
                "duration_days": duration_days,
                "duration_display": format_duration_seconds(duration_seconds),
                "first_activity": str(row["first_activity"]),
                "last_activity": str(row["last_activity"]),
                "has_invalid_timestamps": has_invalid_ts,
            }
        )

    return summaries


def get_case_events(event_df: pd.DataFrame | None, case_id: str) -> pd.DataFrame:
    """Ambil seluruh event untuk satu ``case_id`` dalam urutan timeline stabil.

    Mengembalikan salinan DataFrame yang mempertahankan seluruh kolom asli
    (tanpa memodifikasi ``event_df`` masukan).
    """
    if event_df is None:
        return pd.DataFrame(columns=list(REQUIRED_ATTRIBUTES))

    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return event_df.iloc[0:0].copy()

    target_id = str(case_id)
    mask = event_df[CASE_ID_ATTRIBUTE].notna() & (
        event_df[CASE_ID_ATTRIBUTE].astype(str) == target_id
    )
    case_df = event_df.loc[mask].copy()
    if case_df.empty:
        return case_df.reset_index(drop=True)

    sort_ts_col = "__case_timeline_ts__"
    sort_order_col = "__case_timeline_order__"
    while sort_ts_col in case_df.columns:
        sort_ts_col = f"_{sort_ts_col}"
    while sort_order_col in case_df.columns:
        sort_order_col = f"_{sort_order_col}"

    case_df[sort_ts_col] = _parse_timestamps_utc(case_df[TIMESTAMP_ATTRIBUTE])
    case_df[sort_order_col] = range(len(case_df))
    case_df = (
        case_df.sort_values(
            by=[sort_ts_col, sort_order_col],
            kind="mergesort",
            na_position="last",
        )
        .drop(columns=[sort_ts_col, sort_order_col])
        .reset_index(drop=True)
    )
    return case_df


def get_case_detail(event_df: pd.DataFrame | None, case_id: str) -> dict[str, Any]:
    """Bangun detail lengkap dan timeline terstruktur untuk satu case."""
    target_id = str(case_id)
    if event_df is None:
        return _empty_case_detail(target_id)

    optional_present = validate_event_dataframe(event_df, allow_empty=True)
    has_lifecycle = LIFECYCLE_ATTRIBUTE in optional_present
    has_resource = RESOURCE_ATTRIBUTE in optional_present

    case_df = get_case_events(event_df, target_id)
    if case_df.empty:
        return _empty_case_detail(
            target_id,
            has_lifecycle=has_lifecycle,
            has_resource=has_resource,
        )

    parsed_ts = _parse_timestamps_utc(case_df[TIMESTAMP_ATTRIBUTE])
    has_invalid_ts = bool(parsed_ts.isna().any())

    valid_ts = parsed_ts.dropna()
    first_valid_ts = valid_ts.iloc[0] if not valid_ts.empty else pd.NaT
    if has_invalid_ts or valid_ts.empty:
        start_time = None if has_invalid_ts else format_timestamp(first_valid_ts)
        end_time = None
        duration_seconds: float | None = None
        duration_days: float | None = None
    else:
        start_ts = valid_ts.min()
        end_ts = valid_ts.max()
        start_time = format_timestamp(start_ts)
        end_time = format_timestamp(end_ts)
        duration_seconds = float((end_ts - start_ts).total_seconds())
        duration_days = duration_seconds / SECONDS_PER_DAY

    known_cols = set(REQUIRED_ATTRIBUTES) | set(OPTIONAL_ATTRIBUTES)
    extra_attributes = [
        str(col) for col in case_df.columns if col not in known_cols
    ]

    timeline: list[dict[str, Any]] = []
    prev_ts: Any = pd.NaT
    for idx, row in case_df.iterrows():
        idx_int = int(idx)
        ts = parsed_ts.iloc[idx_int]
        activity = (
            "(missing)"
            if pd.isna(row[ACTIVITY_ATTRIBUTE])
            else str(row[ACTIVITY_ATTRIBUTE])
        )

        if idx_int == 0 or pd.isna(ts) or pd.isna(prev_ts):
            delta_seconds: float | None = 0.0 if (idx_int == 0 and pd.notna(ts)) else None
        else:
            delta_seconds = float((ts - prev_ts).total_seconds())

        if pd.isna(ts) or pd.isna(first_valid_ts):
            elapsed_seconds: float | None = None
        else:
            elapsed_seconds = float((ts - first_valid_ts).total_seconds())

        if pd.notna(ts):
            prev_ts = ts

        extra_map = {
            attr: _clean_value(row[attr]) for attr in extra_attributes
        }
        entry: dict[str, Any] = {
            "step": idx_int + 1,
            "event_index": idx_int,
            "activity": activity,
            "timestamp": format_timestamp(ts),
            "delta_from_prev_seconds": delta_seconds,
            "delta_from_prev_display": format_duration_seconds(delta_seconds),
            "elapsed_from_start_seconds": elapsed_seconds,
            "elapsed_from_start_display": format_duration_seconds(elapsed_seconds),
            "lifecycle": (
                _clean_value(row[LIFECYCLE_ATTRIBUTE]) if has_lifecycle else None
            ),
            "resource": (
                _clean_value(row[RESOURCE_ATTRIBUTE]) if has_resource else None
            ),
            "attributes": extra_map,
        }
        timeline.append(entry)

    activities_series = case_df[ACTIVITY_ATTRIBUTE].where(
        case_df[ACTIVITY_ATTRIBUTE].notna(), "(missing)"
    ).astype(str)

    return {
        "case_id": target_id,
        "found": True,
        "event_count": int(len(case_df)),
        "unique_activities": int(activities_series.nunique()),
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "duration_days": duration_days,
        "duration_display": format_duration_seconds(duration_seconds),
        "first_activity": str(activities_series.iloc[0]),
        "last_activity": str(activities_series.iloc[-1]),
        "has_lifecycle": has_lifecycle,
        "has_resource": has_resource,
        "has_invalid_timestamps": has_invalid_ts,
        "extra_attributes": extra_attributes,
        "timeline": timeline,
    }


def filter_case_summaries(
    summaries: Sequence[dict[str, Any]],
    query: str = "",
    allowed_case_ids: set[str] | Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Saring daftar ringkasan case berdasarkan teks pencarian dan daftar ID."""
    allowed_set = (
        {str(cid) for cid in allowed_case_ids}
        if allowed_case_ids is not None
        else None
    )
    needle = query.strip().lower()

    result: list[dict[str, Any]] = []
    for item in summaries:
        cid = str(item.get("case_id", ""))
        if allowed_set is not None and cid not in allowed_set:
            continue
        if needle and needle not in cid.lower():
            continue
        result.append(item)
    return result


def _empty_case_detail(
    case_id: str,
    *,
    has_lifecycle: bool = False,
    has_resource: bool = False,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "found": False,
        "event_count": 0,
        "unique_activities": 0,
        "start_time": None,
        "end_time": None,
        "duration_seconds": None,
        "duration_days": None,
        "duration_display": "—",
        "first_activity": None,
        "last_activity": None,
        "has_lifecycle": has_lifecycle,
        "has_resource": has_resource,
        "has_invalid_timestamps": False,
        "extra_attributes": [],
        "timeline": [],
    }


__all__ = [
    "build_case_summaries",
    "filter_case_summaries",
    "format_duration_seconds",
    "format_timestamp",
    "get_case_detail",
    "get_case_events",
]
