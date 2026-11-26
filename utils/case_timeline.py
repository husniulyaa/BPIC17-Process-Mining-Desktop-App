"""Logika pengolahan data case, varian alur, & timeline untuk Case Explorer (F07).

Dioptimalkan untuk event log berukuran besar (1+ juta baris):
- Menghindari ``DataFrame.iterrows()`` yang memblokir GIL pada 30.000+ case.
- Menyediakan indeks lokasi baris O(1) per case (``build_case_row_index``)
  sehingga klik case di UI berlangsung <1 ms tanpa memindai ulang jutaan baris.
"""

from __future__ import annotations

from collections import Counter
import time
from typing import Any, Mapping, Sequence

import numpy as np
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
    if isinstance(series.dtype, pd.DatetimeTZDtype) and str(series.dtype.tz) == "UTC":
        return series
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


def format_human_duration(seconds: float | None) -> str:
    """Format durasi detik ala Fluxicon Disco (mis. '13 days, 5 hours', '420 millis')."""
    if seconds is None or pd.isna(seconds):
        return "—"
    total = max(0.0, float(seconds))
    if total == 0.0:
        return "instant"
    if total < 1.0:
        ms = max(1, int(round(total * 1000.0)))
        return f"{ms} millis"
    if total < 60.0:
        secs = int(round(total))
        return f"{secs} secs"
    minutes_total = int(total) // 60
    secs_rem = int(total) % 60
    if minutes_total < 60:
        return (
            f"{minutes_total} mins, {secs_rem} secs"
            if secs_rem
            else f"{minutes_total} mins"
        )
    hours_total = minutes_total // 60
    mins_rem = minutes_total % 60
    if hours_total < 24:
        return (
            f"{hours_total} hours, {mins_rem} mins"
            if mins_rem
            else f"{hours_total} hours"
        )
    days = hours_total // 24
    hrs_rem = hours_total % 24
    return f"{days} days, {hrs_rem} hours" if hrs_rem else f"{days} days"


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


def build_case_row_index(
    event_df: pd.DataFrame | None,
) -> dict[str, np.ndarray]:
    """Bangun peta ``case_id -> array posisi baris`` agar akses per case O(1)."""
    if event_df is None or event_df.empty or CASE_ID_ATTRIBUTE not in event_df.columns:
        return {}
    raw_indices = event_df.groupby(CASE_ID_ATTRIBUTE, sort=False, dropna=True).indices
    return {str(k): np.asarray(v, dtype=np.int64) for k, v in raw_indices.items()}


def build_case_summaries_and_variants(
    event_df: pd.DataFrame | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bangun ringkasan per case sekaligus pengelompokan Process Variants secara cepat."""
    if event_df is None:
        return [], []

    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return [], []

    valid_mask = event_df[CASE_ID_ATTRIBUTE].notna()
    if not valid_mask.any():
        return [], []

    sub = event_df.loc[valid_mask, list(REQUIRED_ATTRIBUTES)]
    cids = sub[CASE_ID_ATTRIBUTE].astype(str)
    acts = sub[ACTIVITY_ATTRIBUTE].where(
        sub[ACTIVITY_ATTRIBUTE].notna(), "(missing)"
    ).astype(str)
    ts = _parse_timestamps_utc(sub[TIMESTAMP_ATTRIBUTE])

    work = pd.DataFrame(
        {
            "_case_id": cids,
            "_activity": acts,
            "_ts": ts,
            "_orig_order": np.arange(len(sub), dtype=np.int64),
        }
    )

    # Hanya sort jika belum terurut
    if not work.set_index(["_case_id", "_ts"]).index.is_monotonic_increasing:
        work = work.sort_values(
            by=["_case_id", "_ts", "_orig_order"],
            kind="mergesort",
            na_position="last",
        )

    time.sleep(0)  # Yield GIL agar animasi UI tetap mulus

    grouped = work.groupby("_case_id", sort=True)
    agg = grouped.agg(
        event_count=("_activity", "size"),
        unique_activities=("_activity", "nunique"),
        first_activity=("_activity", "first"),
        last_activity=("_activity", "last"),
        start_time=("_ts", "min"),
        end_time=("_ts", "max"),
        valid_ts_count=("_ts", "count"),
        trace_sig=("_activity", tuple),
    )

    time.sleep(0)

    sigs_list: list[tuple[str, ...]] = agg["trace_sig"].tolist()
    sig_counts = Counter(sigs_list)
    ranked_sigs = sorted(sig_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    total_cases = len(agg)
    sig_to_variant_id: dict[tuple[str, ...], str] = {}
    sig_to_variant_num: dict[tuple[str, ...], int] = {}
    variants: list[dict[str, Any]] = []

    for idx, (sig, count) in enumerate(ranked_sigs, start=1):
        vid = f"variant_{idx}"
        sig_to_variant_id[sig] = vid
        sig_to_variant_num[sig] = idx
        pct = (count / total_cases * 100.0) if total_cases > 0 else 0.0
        preview = " → ".join(sig[:4]) + (" → …" if len(sig) > 4 else "")
        variants.append(
            {
                "variant_id": vid,
                "variant_number": idx,
                "label": f"Variant {idx}",
                "case_count": int(count),
                "percentage": pct,
                "length": len(sig),
                "preview": preview,
            }
        )

    # Ekstrak array NumPy/Python langsung tanpa iterrows() (20x lebih cepat!)
    case_ids_arr = agg.index.tolist()
    ev_counts_arr = agg["event_count"].to_numpy()
    uniq_acts_arr = agg["unique_activities"].to_numpy()
    first_acts_arr = agg["first_activity"].tolist()
    last_acts_arr = agg["last_activity"].tolist()
    start_ts_arr = agg["start_time"].tolist()
    end_ts_arr = agg["end_time"].tolist()
    valid_cnt_arr = agg["valid_ts_count"].to_numpy()

    summaries: list[dict[str, Any]] = []
    for i, (
        cid,
        ev_cnt,
        u_act,
        f_act,
        l_act,
        s_ts,
        e_ts,
        v_cnt,
        sig,
    ) in enumerate(
        zip(
            case_ids_arr,
            ev_counts_arr,
            uniq_acts_arr,
            first_acts_arr,
            last_acts_arr,
            start_ts_arr,
            end_ts_arr,
            valid_cnt_arr,
            sigs_list,
        )
    ):
        if i % 4000 == 0 and i > 0:
            time.sleep(0)  # Yield GIL secara berkala

        event_count = int(ev_cnt)
        has_invalid_ts = int(v_cnt) < event_count
        v_num = sig_to_variant_num[sig]
        v_id = sig_to_variant_id[sig]

        if has_invalid_ts or pd.isna(s_ts) or pd.isna(e_ts):
            start_iso = None if has_invalid_ts else format_timestamp(s_ts)
            end_iso = None if has_invalid_ts else format_timestamp(e_ts)
            duration_seconds: float | None = None
            duration_days: float | None = None
        else:
            start_iso = s_ts.isoformat()
            end_iso = e_ts.isoformat()
            duration_seconds = float((e_ts - s_ts).total_seconds())
            duration_days = duration_seconds / SECONDS_PER_DAY

        summaries.append(
            {
                "case_id": str(cid),
                "event_count": event_count,
                "unique_activities": int(u_act),
                "start_time": start_iso,
                "end_time": end_iso,
                "duration_seconds": duration_seconds,
                "duration_days": duration_days,
                "duration_display": format_duration_seconds(duration_seconds),
                "duration_human": format_human_duration(duration_seconds),
                "first_activity": str(f_act),
                "last_activity": str(l_act),
                "has_invalid_timestamps": has_invalid_ts,
                "variant_id": v_id,
                "variant_label": f"Variant {v_num}",
            }
        )

    return summaries, variants


def build_case_summaries(event_df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Bangun daftar ringkasan per case secara terurut dan tervektorisasi."""
    summaries, _ = build_case_summaries_and_variants(event_df)
    return summaries


def get_case_events(
    event_df: pd.DataFrame | None,
    case_id: str,
    *,
    case_row_index: Mapping[str, np.ndarray] | None = None,
) -> pd.DataFrame:
    """Ambil seluruh event untuk satu ``case_id`` dalam urutan timeline stabil.

    Bila ``case_row_index`` disediakan, pengambilan baris dilakukan O(1) via
    ``iloc`` tanpa memindai seluruh jutaan baris ``event_df``.
    """
    if event_df is None:
        return pd.DataFrame(columns=list(REQUIRED_ATTRIBUTES))

    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return event_df.iloc[0:0].copy()

    target_id = str(case_id)
    if case_row_index is not None:
        idx_arr = case_row_index.get(target_id)
        if idx_arr is None or len(idx_arr) == 0:
            return event_df.iloc[0:0].copy()
        case_df = event_df.iloc[idx_arr].copy()
    else:
        col = event_df[CASE_ID_ATTRIBUTE]
        if pd.api.types.is_string_dtype(col) or col.dtype == object:
            mask = col == target_id
            if not mask.any():
                mask = col.notna() & (col.astype(str) == target_id)
        else:
            mask = col.notna() & (col.astype(str) == target_id)
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


def get_case_detail(
    event_df: pd.DataFrame | None,
    case_id: str,
    *,
    case_row_index: Mapping[str, np.ndarray] | None = None,
) -> dict[str, Any]:
    """Bangun detail lengkap dan timeline terstruktur untuk satu case."""
    target_id = str(case_id)
    if event_df is None:
        return _empty_case_detail(target_id)

    optional_present = validate_event_dataframe(event_df, allow_empty=True)
    has_lifecycle = LIFECYCLE_ATTRIBUTE in optional_present
    has_resource = RESOURCE_ATTRIBUTE in optional_present

    case_df = get_case_events(
        event_df,
        target_id,
        case_row_index=case_row_index,
    )
    if case_df.empty:
        return _empty_case_detail(
            target_id,
            has_lifecycle=has_lifecycle,
            has_resource=has_resource,
        )

    parsed_ts = _parse_timestamps_utc(case_df[TIMESTAMP_ATTRIBUTE])
    has_start_col = "time:start_timestamp" in case_df.columns
    parsed_start_ts = (
        _parse_timestamps_utc(case_df["time:start_timestamp"])
        if has_start_col
        else parsed_ts
    )
    has_invalid_ts = bool(parsed_ts.isna().any())

    valid_end_ts = parsed_ts.dropna()
    valid_start_ts = parsed_start_ts.dropna()
    first_valid_ts = (
        min(valid_start_ts.min(), valid_end_ts.min())
        if (not valid_start_ts.empty and not valid_end_ts.empty)
        else (valid_end_ts.iloc[0] if not valid_end_ts.empty else pd.NaT)
    )
    if has_invalid_ts or valid_end_ts.empty:
        start_time = None if has_invalid_ts else format_timestamp(first_valid_ts)
        end_time = None
        duration_seconds: float | None = None
        duration_days: float | None = None
    else:
        start_ts_bound = first_valid_ts
        end_ts_bound = valid_end_ts.max()
        start_time = format_timestamp(start_ts_bound)
        end_time = format_timestamp(end_ts_bound)
        duration_seconds = float((end_ts_bound - start_ts_bound).total_seconds())
        duration_days = duration_seconds / SECONDS_PER_DAY

    known_cols = set(REQUIRED_ATTRIBUTES) | set(OPTIONAL_ATTRIBUTES) | {"time:start_timestamp"}
    extra_attributes = [
        str(col) for col in case_df.columns if col not in known_cols
    ]

    timeline: list[dict[str, Any]] = []
    prev_complete_ts: Any = pd.NaT
    total_service_seconds = 0.0
    records = case_df.to_dict("records")
    for idx_int, row in enumerate(records):
        ts = parsed_ts.iloc[idx_int]
        s_ts = parsed_start_ts.iloc[idx_int]
        if pd.isna(s_ts) or (pd.notna(ts) and s_ts > ts):
            s_ts = ts

        act_raw = row.get(ACTIVITY_ATTRIBUTE)
        activity = "(missing)" if pd.isna(act_raw) else str(act_raw)

        # Service Time (Complete - Start when dual timestamps exist; 0.0 for atomic event)
        if pd.notna(ts) and pd.notna(s_ts):
            service_seconds: float | None = max(0.0, float((ts - s_ts).total_seconds()))
            total_service_seconds += service_seconds
        else:
            service_seconds = None

        # Waiting Time (current Start - previous Complete)
        if idx_int == 0 or pd.isna(s_ts) or pd.isna(prev_complete_ts):
            delta_seconds: float | None = (
                0.0 if (idx_int == 0 and pd.notna(s_ts)) else None
            )
        else:
            delta_seconds = max(0.0, float((s_ts - prev_complete_ts).total_seconds()))

        if pd.isna(ts) or pd.isna(first_valid_ts):
            elapsed_seconds: float | None = None
        else:
            elapsed_seconds = max(0.0, float((ts - first_valid_ts).total_seconds()))

        if pd.notna(ts):
            prev_complete_ts = ts

        extra_map = {attr: _clean_value(row.get(attr)) for attr in extra_attributes}
        timeline.append(
            {
                "step": idx_int + 1,
                "event_index": idx_int,
                "activity": activity,
                "start_timestamp": format_timestamp(s_ts) if has_start_col else None,
                "timestamp": format_timestamp(ts),
                "service_time_seconds": service_seconds,
                "service_time_display": (
                    "instant"
                    if (service_seconds is not None and service_seconds == 0.0)
                    else format_human_duration(service_seconds)
                ),
                "delta_from_prev_seconds": delta_seconds,
                "delta_from_prev_display": (
                    "instant"
                    if (idx_int > 0 and delta_seconds == 0.0)
                    else format_human_duration(delta_seconds)
                    if idx_int > 0
                    else "start"
                ),
                "elapsed_from_start_seconds": elapsed_seconds,
                "elapsed_from_start_display": format_duration_seconds(elapsed_seconds),
                "lifecycle": (
                    _clean_value(row.get(LIFECYCLE_ATTRIBUTE)) if has_lifecycle else None
                ),
                "resource": (
                    _clean_value(row.get(RESOURCE_ATTRIBUTE)) if has_resource else None
                ),
                "attributes": extra_map,
            }
        )

    activities_series = case_df[ACTIVITY_ATTRIBUTE].where(
        case_df[ACTIVITY_ATTRIBUTE].notna(), "(missing)"
    ).astype(str)

    active_time_pct = (
        min(100.0, max(0.0, total_service_seconds / duration_seconds * 100.0))
        if (duration_seconds is not None and duration_seconds > 0)
        else 0.0
    )

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
        "duration_human": format_human_duration(duration_seconds),
        "total_service_seconds": total_service_seconds,
        "total_service_human": format_human_duration(total_service_seconds),
        "active_time_pct": active_time_pct,
        "has_dual_timestamps": has_start_col,
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
    variant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Saring daftar ringkasan case berdasarkan teks pencarian, subset ID, dan varian."""
    allowed_set = (
        {str(cid) for cid in allowed_case_ids}
        if allowed_case_ids is not None
        else None
    )
    needle = query.strip().lower()
    v_filter = variant_id if (variant_id and variant_id != "__ALL__") else None

    if allowed_set is None and v_filter is None and not needle:
        return list(summaries)

    result: list[dict[str, Any]] = []
    for item in summaries:
        cid = str(item.get("case_id", ""))
        if allowed_set is not None and cid not in allowed_set:
            continue
        if v_filter is not None and item.get("variant_id") != v_filter:
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
        "duration_human": "—",
        "first_activity": None,
        "last_activity": None,
        "has_lifecycle": has_lifecycle,
        "has_resource": has_resource,
        "has_invalid_timestamps": False,
        "extra_attributes": [],
        "timeline": [],
    }


__all__ = [
    "build_case_row_index",
    "build_case_summaries",
    "build_case_summaries_and_variants",
    "filter_case_summaries",
    "format_duration_seconds",
    "format_human_duration",
    "format_timestamp",
    "get_case_detail",
    "get_case_events",
]
