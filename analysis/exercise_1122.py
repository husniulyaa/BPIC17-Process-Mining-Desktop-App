"""Analisis Exercise 11.22 untuk event log BPIC17.

Mengidentifikasi case unik yang memiliki event ``O_Cancelled`` dan kemudian,
pada timestamp yang secara ketat lebih akhir (``t_accepted > t_cancelled``),
memiliki event ``O_Accepted`` dalam case yang sama.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)

EXERCISE_1122_ID = "11.22"
CANCELLED_ACTIVITY = "O_Cancelled"
ACCEPTED_ACTIVITY = "O_Accepted"
LIFECYCLE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[0]  # "lifecycle:transition"
RESOURCE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[1]  # "org:resource"
SECONDS_PER_DAY = 86400.0

EXERCISE_1122_RULE = (
    "Identifikasi case unik yang memiliki event 'O_Cancelled' dan kemudian, "
    "pada waktu (timestamp) yang lebih akhir, memiliki event 'O_Accepted' "
    "dalam case yang sama. Keduanya tidak harus bersebelahan (event lain "
    "di antara keduanya diperbolehkan). Jika 'O_Cancelled' dan 'O_Accepted' "
    "memiliki timestamp persis sama tanpa ada 'O_Accepted' pada waktu lebih "
    "akhir, case tidak dihitung karena urutan waktu tidak dapat dipastikan "
    "dari timestamp."
)

EXERCISE_1122_ASSUMPTIONS = [
    (
        "Event dalam setiap case diurutkan secara stabil berdasarkan "
        "time:timestamp (UTC) diikuti urutan asli pada DataFrame."
    ),
    (
        "Perbandingan waktu bersifat ketat (timestamp O_Accepted > timestamp "
        "O_Cancelled). Pasangan dengan timestamp sama tidak dianggap memenuhi "
        "syarat dan dicatat terpisah pada field 'same_timestamp_cases'."
    ),
    (
        "Event dengan timestamp tidak valid (NaT) tidak digunakan untuk "
        "membuktikan urutan waktu dan dicatat pada field 'warnings'."
    ),
    (
        "O_Cancelled dan O_Accepted tidak harus bersebelahan; jumlah event "
        "perantara dicatat pada 'events_between_count'."
    ),
    (
        "Atribut opsional (lifecycle:transition, org:resource) tidak wajib "
        "untuk Exercise 11.22 dan hanya disertakan pada evidence jika tersedia "
        "pada DataFrame."
    ),
]


def _parse_timestamps_utc(series: pd.Series) -> pd.Series:
    """Konversi kolom timestamp ke datetime UTC secara aman tanpa mutasi."""
    try:
        return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce", utc=True)


def _format_timestamp(value: Any) -> str | None:
    """Format timestamp menjadi ISO-8601 string atau None jika NaT/kosong."""
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _format_duration_seconds(seconds: float | None) -> str:
    """Format durasi dalam detik menjadi teks ringkas yang mudah dibaca."""
    if seconds is None or pd.isna(seconds):
        return "—"
    total_seconds = max(0.0, float(seconds))
    days, rem = divmod(int(total_seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _clean_optional_value(value: Any) -> str | None:
    """Normalkan nilai atribut opsional tanpa memalsukan nilai kosong."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def _build_empty_result(
    total_cases_in_log: int = 0,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "exercise": EXERCISE_1122_ID,
        "rule": EXERCISE_1122_RULE,
        "total_cases": 0,
        "total_cases_in_log": int(total_cases_in_log),
        "case_ids": [],
        "details": [],
        "same_timestamp_cases": [],
        "warnings": list(warnings) if warnings else [],
        "assumptions": list(EXERCISE_1122_ASSUMPTIONS),
    }


def _event_record(
    *,
    event_index: int,
    activity: str,
    timestamp: Any,
    has_lifecycle: bool,
    lifecycle_value: Any = None,
    has_resource: bool = False,
    resource_value: Any = None,
    role: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "event_index": int(event_index),
        "step": int(event_index) + 1,
        "activity": activity,
        "timestamp": _format_timestamp(timestamp),
    }
    if role is not None:
        record["role"] = role
    if has_lifecycle:
        record[LIFECYCLE_ATTRIBUTE] = _clean_optional_value(lifecycle_value)
    if has_resource:
        record[RESOURCE_ATTRIBUTE] = _clean_optional_value(resource_value)
    return record


def analyze_exercise_1122(event_df: pd.DataFrame | None) -> dict[str, Any]:
    """Analisis Exercise 11.22 dari DataFrame event log BPIC17.

    Mencari seluruh case unik yang memiliki minimal satu event ``O_Cancelled``
    dan diikuti pada waktu yang lebih akhir (``timestamp O_Accepted >
    timestamp O_Cancelled``) oleh minimal satu event ``O_Accepted`` dalam case
    yang sama.

    Args:
        event_df: Pandas DataFrame dengan kolom inti ``case:concept:name``,
            ``concept:name``, dan ``time:timestamp``. DataFrame masukan tidak
            dimodifikasi.

    Returns:
        Dict hasil analisis terstruktur sesuai ``TEAM_BASELINE.md`` dengan key
        utama ``exercise``, ``rule``, ``total_cases``, ``case_ids``, dan
        ``details``, ditambah ``total_cases_in_log``, ``same_timestamp_cases``,
        ``warnings``, dan ``assumptions``.

    Raises:
        TypeError: Jika ``event_df`` bukan Pandas DataFrame (dan bukan ``None``).
        ValueError: Jika kolom inti XES yang wajib tidak tersedia.
    """
    if event_df is None:
        return _build_empty_result()

    optional_present = validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return _build_empty_result()

    has_lifecycle = LIFECYCLE_ATTRIBUTE in optional_present
    has_resource = RESOURCE_ATTRIBUTE in optional_present

    cols_to_copy = [CASE_ID_ATTRIBUTE, ACTIVITY_ATTRIBUTE, TIMESTAMP_ATTRIBUTE]
    if has_lifecycle:
        cols_to_copy.append(LIFECYCLE_ATTRIBUTE)
    if has_resource:
        cols_to_copy.append(RESOURCE_ATTRIBUTE)

    df = event_df[cols_to_copy].copy()
    warnings: list[str] = []

    # Tangani baris dengan case ID kosong secara eksplisit.
    missing_case_mask = df[CASE_ID_ATTRIBUTE].isna()
    if missing_case_mask.any():
        missing_count = int(missing_case_mask.sum())
        warnings.append(
            f"Ditemukan {missing_count} event tanpa '{CASE_ID_ATTRIBUTE}' "
            "yang diabaikan dari analisis."
        )
        df = df.loc[~missing_case_mask].copy()
        if df.empty:
            return _build_empty_result(total_cases_in_log=0, warnings=warnings)

    df["_case_id"] = df[CASE_ID_ATTRIBUTE].astype(str)
    df["_activity"] = df[ACTIVITY_ATTRIBUTE].where(
        df[ACTIVITY_ATTRIBUTE].notna(), ""
    ).astype(str).str.strip()
    df["_ts"] = _parse_timestamps_utc(df[TIMESTAMP_ATTRIBUTE])
    df["_orig_order"] = range(len(df))

    total_cases_in_log = int(df["_case_id"].nunique())

    nat_total = int(df["_ts"].isna().sum())
    if nat_total > 0:
        warnings.append(
            f"Terdapat {nat_total} event dengan timestamp tidak valid (NaT); "
            "event tersebut tidak digunakan untuk menentukan urutan waktu."
        )

    # Pre-filter cepat: hanya case yang memuat O_Cancelled DAN O_Accepted.
    cancelled_cases = set(df.loc[df["_activity"] == CANCELLED_ACTIVITY, "_case_id"])
    accepted_cases = set(df.loc[df["_activity"] == ACCEPTED_ACTIVITY, "_case_id"])
    candidate_cases = cancelled_cases & accepted_cases

    if not candidate_cases:
        return _build_empty_result(
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    # Urutkan hanya event milik case kandidat secara stabil.
    cand_df = (
        df.loc[df["_case_id"].isin(candidate_cases)]
        .sort_values(
            by=["_case_id", "_ts", "_orig_order"],
            kind="mergesort",
            na_position="last",
        )
        .reset_index(drop=True)
    )

    matched_case_ids: list[str] = []
    details: list[dict[str, Any]] = []
    same_timestamp_cases: list[str] = []
    target_nat_cases: list[str] = []

    for case_id, group in cand_df.groupby("_case_id", sort=True):
        group = group.reset_index(drop=True)
        activities = group["_activity"]
        timestamps = group["_ts"]

        cancelled_rows = group.loc[activities == CANCELLED_ACTIVITY]
        accepted_rows = group.loc[activities == ACCEPTED_ACTIVITY]

        valid_cancelled = cancelled_rows.loc[cancelled_rows["_ts"].notna()]
        valid_accepted = accepted_rows.loc[accepted_rows["_ts"].notna()]

        if len(valid_cancelled) < len(cancelled_rows) or len(valid_accepted) < len(accepted_rows):
            target_nat_cases.append(str(case_id))

        if valid_cancelled.empty or valid_accepted.empty:
            continue

        first_cancel_idx = int(valid_cancelled.index[0])
        first_cancel_ts = valid_cancelled.iloc[0]["_ts"]

        later_accepted = valid_accepted.loc[valid_accepted["_ts"] > first_cancel_ts]
        if later_accepted.empty:
            # Cek apakah ada pasangan O_Cancelled & O_Accepted dengan timestamp sama.
            cancel_ts_set = set(valid_cancelled["_ts"])
            if any(ts in cancel_ts_set for ts in valid_accepted["_ts"]):
                same_timestamp_cases.append(str(case_id))
            continue

        first_later_accept_idx = int(later_accepted.index[0])
        first_later_accept_ts = later_accepted.iloc[0]["_ts"]
        last_later_accept_ts = later_accepted.iloc[-1]["_ts"]

        delta_seconds = float(
            (first_later_accept_ts - first_cancel_ts).total_seconds()
        )
        events_between = max(0, first_later_accept_idx - first_cancel_idx - 1)

        # Susun daftar event bukti (semua O_Cancelled dan O_Accepted pada case).
        evidence_events: list[dict[str, Any]] = []
        target_rows = group.loc[
            activities.isin((CANCELLED_ACTIVITY, ACCEPTED_ACTIVITY))
        ]
        for idx, row in target_rows.iterrows():
            idx_int = int(idx)
            act = str(row["_activity"])
            role = "target_event"
            if idx_int == first_cancel_idx:
                role = "first_o_cancelled"
            elif idx_int == first_later_accept_idx:
                role = "first_o_accepted_after_cancelled"
            elif act == ACCEPTED_ACTIVITY and pd.notna(row["_ts"]) and row["_ts"] > first_cancel_ts:
                role = "o_accepted_after_cancelled"
            elif act == ACCEPTED_ACTIVITY and pd.notna(row["_ts"]) and row["_ts"] <= first_cancel_ts:
                role = "o_accepted_not_after_cancelled"
            elif act == CANCELLED_ACTIVITY:
                role = "o_cancelled"

            evidence_events.append(
                _event_record(
                    event_index=idx_int,
                    activity=act,
                    timestamp=row["_ts"],
                    has_lifecycle=has_lifecycle,
                    lifecycle_value=row[LIFECYCLE_ATTRIBUTE] if has_lifecycle else None,
                    has_resource=has_resource,
                    resource_value=row[RESOURCE_ATTRIBUTE] if has_resource else None,
                    role=role,
                )
            )

        # Cuplikan timeline dari O_Cancelled pertama hingga O_Accepted pertama setelahnya.
        slice_start = min(first_cancel_idx, first_later_accept_idx)
        slice_end = max(first_cancel_idx, first_later_accept_idx)
        timeline_excerpt: list[dict[str, Any]] = []
        for idx, row in group.iloc[slice_start : slice_end + 1].iterrows():
            idx_int = int(idx)
            act = str(row["_activity"])
            if idx_int == first_cancel_idx:
                excerpt_role = "first_o_cancelled"
            elif idx_int == first_later_accept_idx:
                excerpt_role = "first_o_accepted_after_cancelled"
            else:
                excerpt_role = "intermediate"
            timeline_excerpt.append(
                _event_record(
                    event_index=idx_int,
                    activity=act,
                    timestamp=row["_ts"],
                    has_lifecycle=has_lifecycle,
                    lifecycle_value=row[LIFECYCLE_ATTRIBUTE] if has_lifecycle else None,
                    has_resource=has_resource,
                    resource_value=row[RESOURCE_ATTRIBUTE] if has_resource else None,
                    role=excerpt_role,
                )
            )

        case_id_str = str(case_id)
        matched_case_ids.append(case_id_str)
        details.append(
            {
                "case_id": case_id_str,
                "first_cancelled_timestamp": _format_timestamp(first_cancel_ts),
                "first_cancelled_index": first_cancel_idx,
                "first_accepted_after_cancelled_timestamp": _format_timestamp(
                    first_later_accept_ts
                ),
                "first_accepted_after_cancelled_index": first_later_accept_idx,
                "last_accepted_after_cancelled_timestamp": _format_timestamp(
                    last_later_accept_ts
                ),
                "time_between_seconds": delta_seconds,
                "time_between_days": delta_seconds / SECONDS_PER_DAY,
                "time_between_display": _format_duration_seconds(delta_seconds),
                "events_between_count": events_between,
                "cancelled_count": int(len(cancelled_rows)),
                "accepted_count": int(len(accepted_rows)),
                "accepted_after_cancelled_count": int(len(later_accepted)),
                "total_events": int(len(group)),
                "evidence_events": evidence_events,
                "timeline_excerpt": timeline_excerpt,
            }
        )

    if same_timestamp_cases:
        warnings.append(
            f"{len(same_timestamp_cases)} case memiliki 'O_Cancelled' dan "
            "'O_Accepted' pada timestamp persis sama tanpa ada 'O_Accepted' "
            "yang lebih akhir sehingga tidak dimasukkan ke hasil (lihat "
            "'same_timestamp_cases')."
        )
    if target_nat_cases:
        warnings.append(
            f"{len(target_nat_cases)} case kandidat memiliki event target "
            "('O_Cancelled'/'O_Accepted') dengan timestamp tidak valid (NaT)."
        )

    return {
        "exercise": EXERCISE_1122_ID,
        "rule": EXERCISE_1122_RULE,
        "total_cases": len(matched_case_ids),
        "total_cases_in_log": total_cases_in_log,
        "case_ids": matched_case_ids,
        "details": details,
        "same_timestamp_cases": same_timestamp_cases,
        "warnings": warnings,
        "assumptions": list(EXERCISE_1122_ASSUMPTIONS),
    }


__all__ = [
    "ACCEPTED_ACTIVITY",
    "CANCELLED_ACTIVITY",
    "EXERCISE_1122_ASSUMPTIONS",
    "EXERCISE_1122_ID",
    "EXERCISE_1122_RULE",
    "analyze_exercise_1122",
]
