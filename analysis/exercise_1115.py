"""Analisis Exercise 11.15 untuk event log BPIC17.

Menghitung jumlah case unik di mana aktivitas ``W_Assess Potential Fraud``
berstatus ``complete`` minimal 2 kali dalam satu case.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

TARGET_ACTIVITY = "W_Assess Potential Fraud"
COMPLETE_LIFECYCLE = "complete"
MIN_OCCURRENCES = 2

CASE_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIMESTAMP_COL = "time:timestamp"
LIFECYCLE_COL = "lifecycle:transition"
RESOURCE_COL = "org:resource"
EVENT_ID_COL = "EventID"

CORE_COLUMNS = (CASE_COL, ACTIVITY_COL, TIMESTAMP_COL)

EXERCISE_1115_ID = "11.15"
EXERCISE_1115_RULE = (
    "Menghitung jumlah case unik yang memiliki minimal 2 event aktivitas "
    f"'{TARGET_ACTIVITY}' (pencocokan case-insensitive dan strip whitespace) "
    f"dengan lifecycle:transition = '{COMPLETE_LIFECYCLE}' (case-insensitive)."
)
DENOMINATOR_NOTE = (
    "Denominator adalah jumlah seluruh case unik (case:concept:name) "
    "pada DataFrame event log masukan."
)


def build_empty_result(
    exercise: str,
    rule: str,
    total_cases_in_log: int = 0,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Membangun struktur hasil standar ketika tidak ada case yang lolos atau terjadi keterbatasan data.

    Catatan field tambahan (usulan untuk disepakati tim):
    - ``total_cases_in_log``: jumlah seluruh case unik pada event_df masukan.
    - ``denominator_note``: penjelasan arti denominator.
    - ``warnings``: daftar pesan peringatan/keterbatasan data.
    """
    return {
        "exercise": exercise,
        "rule": rule,
        "total_cases": 0,
        "case_ids": [],
        "details": [],
        "total_cases_in_log": int(total_cases_in_log),
        "denominator_note": DENOMINATOR_NOTE,
        "warnings": list(warnings) if warnings else [],
    }


def _format_timestamp(value: Any) -> str | None:
    """Mengubah nilai timestamp menjadi string ISO-8601 atau None jika NaT/kosong."""
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def build_evidence_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Menyusun daftar dict bukti event dari DataFrame yang sudah terurut."""
    has_resource = RESOURCE_COL in df.columns
    has_event_id = EVENT_ID_COL in df.columns

    records: list[dict[str, Any]] = []
    cols = [TIMESTAMP_COL, ACTIVITY_COL, LIFECYCLE_COL]
    if has_resource:
        cols.append(RESOURCE_COL)
    if has_event_id:
        cols.append(EVENT_ID_COL)

    for item in df[cols].to_dict(orient="records"):
        evidence_item: dict[str, Any] = {
            "timestamp": _format_timestamp(item.get(TIMESTAMP_COL)),
            "activity": None if pd.isna(item.get(ACTIVITY_COL)) else str(item.get(ACTIVITY_COL)),
            "lifecycle": None if pd.isna(item.get(LIFECYCLE_COL)) else str(item.get(LIFECYCLE_COL)),
            "resource": (
                None
                if not has_resource or pd.isna(item.get(RESOURCE_COL))
                else str(item.get(RESOURCE_COL))
            ),
        }
        if has_event_id:
            raw_eid = item.get(EVENT_ID_COL)
            evidence_item["EventID"] = None if pd.isna(raw_eid) else raw_eid
        records.append(evidence_item)
    return records


def prepare_target_complete_events(
    event_df: pd.DataFrame,
    require_resource: bool = False,
) -> tuple[pd.DataFrame | None, int, list[str]]:
    """Memvalidasi event_df dan mengekstrak event target berstatus complete secara terurut.

    Fungsi ini tidak memodifikasi ``event_df`` masukan.

    Returns:
        Tuple ``(filtered_sorted_df, total_cases_in_log, warnings)``.
        Jika validasi gagal atau dataset kosong, ``filtered_sorted_df`` bernilai ``None``.
    """
    warnings: list[str] = []

    if event_df is None or not isinstance(event_df, pd.DataFrame):
        warnings.append("Input event_df tidak valid atau bernilai None.")
        return None, 0, warnings

    missing_core = [col for col in CORE_COLUMNS if col not in event_df.columns]
    if missing_core:
        warnings.append(
            "Kolom inti tidak lengkap pada event_df: " + ", ".join(missing_core) + "."
        )
        return None, 0, warnings

    total_cases_in_log = int(event_df[CASE_COL].nunique(dropna=True))

    if event_df.empty:
        warnings.append("Dataset event log kosong.")
        return None, total_cases_in_log, warnings

    if LIFECYCLE_COL not in event_df.columns:
        warnings.append(
            f"Kolom '{LIFECYCLE_COL}' tidak ditemukan; event '{COMPLETE_LIFECYCLE}' "
            "tidak dapat diidentifikasi secara valid."
        )
        return None, total_cases_in_log, warnings

    if require_resource and RESOURCE_COL not in event_df.columns:
        warnings.append(
            f"Kolom '{RESOURCE_COL}' tidak ditemukan; kesamaan resource tidak dapat dievaluasi."
        )
        return None, total_cases_in_log, warnings

    target_norm = TARGET_ACTIVITY.strip().lower()
    complete_norm = COMPLETE_LIFECYCLE.strip().lower()

    activity_norm = event_df[ACTIVITY_COL].astype("string").str.strip().str.lower()
    lifecycle_norm = event_df[LIFECYCLE_COL].astype("string").str.strip().str.lower()

    mask = (activity_norm == target_norm) & (lifecycle_norm == complete_norm)
    mask = mask.fillna(False)

    if not bool(mask.any()):
        return event_df.iloc[0:0].copy(), total_cases_in_log, warnings

    filtered = event_df.loc[mask].copy()

    # Simpan urutan baris asli sebagai tie-breaker stabil sebelum sorting
    row_order_col = "__orig_row_order__"
    while row_order_col in filtered.columns:
        row_order_col = f"_{row_order_col}"
    filtered[row_order_col] = pd.RangeIndex(len(event_df))[mask.to_numpy()]

    # Konversi time:timestamp ke datetime UTC secara aman jika belum datetime/tz-aware
    ts_series = filtered[TIMESTAMP_COL]
    raw_non_null = int(ts_series.notna().sum())
    parsed_ts = pd.to_datetime(ts_series, utc=True, errors="coerce")
    if int(parsed_ts.notna().sum()) < raw_non_null:
        warnings.append(
            "Sebagian nilai 'time:timestamp' pada event target tidak dapat dikonversi ke datetime."
        )
    filtered[TIMESTAMP_COL] = parsed_ts

    filtered = filtered.sort_values(
        by=[CASE_COL, TIMESTAMP_COL, row_order_col],
        kind="mergesort",
        na_position="last",
    )
    filtered = filtered.drop(columns=[row_order_col])

    return filtered, total_cases_in_log, warnings


def analyze_exercise_1115(event_df: pd.DataFrame) -> dict[str, Any]:
    """Menganalisis Exercise 11.15 pada event log BPIC17.

    Menghitung jumlah case unik dengan minimal 2 event
    ``W_Assess Potential Fraud`` berstatus ``complete``.

    Field tambahan di luar kontrak dasar (usulan untuk disepakati tim):
    - ``total_cases_in_log`` (int): jumlah seluruh case unik sebagai denominator.
    - ``denominator_note`` (str): keterangan denominator.
    - ``warnings`` (list[str]): pesan peringatan/keterbatasan data.
    """
    filtered, total_cases_in_log, warnings = prepare_target_complete_events(
        event_df,
        require_resource=False,
    )
    if filtered is None or filtered.empty:
        return build_empty_result(
            exercise=EXERCISE_1115_ID,
            rule=EXERCISE_1115_RULE,
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    counts = filtered.groupby(CASE_COL, sort=False).size()
    qualifying_counts = counts[counts >= MIN_OCCURRENCES]

    if qualifying_counts.empty:
        return build_empty_result(
            exercise=EXERCISE_1115_ID,
            rule=EXERCISE_1115_RULE,
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    qualifying_case_ids = sorted(qualifying_counts.index.tolist(), key=lambda x: str(x))
    qualifying_df = filtered[filtered[CASE_COL].isin(qualifying_counts.index)]

    grouped_cases = {
        case_id: group_df
        for case_id, group_df in qualifying_df.groupby(CASE_COL, sort=False)
    }

    details: list[dict[str, Any]] = []
    for case_id in qualifying_case_ids:
        case_df = grouped_cases[case_id]
        details.append(
            {
                "case_id": case_id,
                "complete_count": int(qualifying_counts[case_id]),
                "evidence": build_evidence_records(case_df),
            }
        )

    return {
        "exercise": EXERCISE_1115_ID,
        "rule": EXERCISE_1115_RULE,
        "total_cases": len(qualifying_case_ids),
        "case_ids": qualifying_case_ids,
        "details": details,
        "total_cases_in_log": total_cases_in_log,
        "denominator_note": DENOMINATOR_NOTE,
        "warnings": warnings,
    }
