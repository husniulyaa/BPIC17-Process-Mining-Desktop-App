"""Analisis Exercise 11.18 untuk event log BPIC17.

Menghitung jumlah case unik di mana aktivitas ``W_Assess Potential Fraud``
berstatus ``complete`` minimal 2 kali oleh resource (``org:resource``) yang sama
dan tidak kosong dalam satu case.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from analysis.exercise_1115 import (
    CASE_COL,
    COMPLETE_LIFECYCLE,
    DENOMINATOR_NOTE,
    MIN_OCCURRENCES,
    RESOURCE_COL,
    TARGET_ACTIVITY,
    build_empty_result,
    build_evidence_records,
    prepare_target_complete_events,
)

EXERCISE_1118_ID = "11.18"
EXERCISE_1118_RULE = (
    "Menghitung jumlah case unik yang memiliki minimal 2 event aktivitas "
    f"'{TARGET_ACTIVITY}' (case-insensitive, strip whitespace) dengan "
    f"lifecycle:transition = '{COMPLETE_LIFECYCLE}' oleh org:resource yang sama "
    "(identik dan tidak kosong/NaN) dalam satu case."
)


def analyze_exercise_1118(event_df: pd.DataFrame) -> dict[str, Any]:
    """Menganalisis Exercise 11.18 pada event log BPIC17.

    Memfilter event target berstatus ``complete``, mengabaikan resource kosong/NaN,
    lalu mencari pasangan ``(case_id, resource)`` dengan jumlah occurrence >= 2.

    Field tambahan di luar kontrak dasar (usulan untuk disepakati tim):
    - ``total_cases_in_log`` (int): jumlah seluruh case unik sebagai denominator.
    - ``denominator_note`` (str): keterangan denominator.
    - ``warnings`` (list[str]): pesan peringatan/keterbatasan data.
    """
    filtered, total_cases_in_log, warnings = prepare_target_complete_events(
        event_df,
        require_resource=True,
    )
    if filtered is None or filtered.empty:
        return build_empty_result(
            exercise=EXERCISE_1118_ID,
            rule=EXERCISE_1118_RULE,
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    res_series = filtered[RESOURCE_COL]
    res_stripped = res_series.astype("string").str.strip()
    is_empty_resource = res_series.isna() | (res_stripped == "")
    empty_count = int(is_empty_resource.sum())

    if empty_count > 0:
        warnings.append(
            f"Ditemukan {empty_count} event target berstatus '{COMPLETE_LIFECYCLE}' "
            "dengan org:resource kosong/NaN; event tersebut dilewati dan tidak "
            "dikelompokkan sebagai resource yang sama."
        )

    valid_df = filtered.loc[~is_empty_resource].copy()
    if valid_df.empty:
        return build_empty_result(
            exercise=EXERCISE_1118_ID,
            rule=EXERCISE_1118_RULE,
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    clean_res_col = "__resource_clean__"
    while clean_res_col in valid_df.columns:
        clean_res_col = f"_{clean_res_col}"
    valid_df[clean_res_col] = valid_df[RESOURCE_COL].astype("string").str.strip()

    pair_counts = valid_df.groupby([CASE_COL, clean_res_col], sort=False).size()
    qualifying_pairs = pair_counts[pair_counts >= MIN_OCCURRENCES]

    if qualifying_pairs.empty:
        return build_empty_result(
            exercise=EXERCISE_1118_ID,
            rule=EXERCISE_1118_RULE,
            total_cases_in_log=total_cases_in_log,
            warnings=warnings,
        )

    sorted_pairs = sorted(
        qualifying_pairs.index.tolist(),
        key=lambda pair: (str(pair[0]), str(pair[1])),
    )
    case_ids = sorted(
        {pair[0] for pair in sorted_pairs},
        key=lambda cid: str(cid),
    )

    qualifying_set = set(sorted_pairs)
    grouped_pairs: dict[tuple[Any, Any], pd.DataFrame] = {}
    for pair_key, group_df in valid_df.groupby([CASE_COL, clean_res_col], sort=False):
        if pair_key in qualifying_set:
            grouped_pairs[pair_key] = group_df

    details: list[dict[str, Any]] = []
    for case_id, resource in sorted_pairs:
        pair_df = grouped_pairs[(case_id, resource)]
        details.append(
            {
                "case_id": case_id,
                "resource": str(resource),
                "complete_count_by_resource": int(qualifying_pairs[(case_id, resource)]),
                "evidence": build_evidence_records(pair_df),
            }
        )

    return {
        "exercise": EXERCISE_1118_ID,
        "rule": EXERCISE_1118_RULE,
        "total_cases": len(case_ids),
        "case_ids": case_ids,
        "details": details,
        "total_cases_in_log": total_cases_in_log,
        "denominator_note": DENOMINATOR_NOTE,
        "warnings": warnings,
    }
