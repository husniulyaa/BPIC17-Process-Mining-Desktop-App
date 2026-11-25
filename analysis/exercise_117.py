from __future__ import annotations

from typing import Any

import pandas as pd

CASE_COL = "case:concept:name"
ACT_COL = "concept:name"
TS_COL = "time:timestamp"
REQUIRED_COLUMNS = (CASE_COL, ACT_COL, TS_COL)
SECONDS_PER_DAY = 86400.0

ACCEPTED = "O_Accepted"
REFUSED = "O_Refused"
CANCELLED = "O_Cancelled"

SUBQUESTIONS = ("11.7 A", "11.7 B", "11.7 C", "11.7 D", "11.7 E")

TITLES = {
    "11.7 A": "Total Cases",
    "11.7 B": "Mean Cycle Time (All Cases)",
    "11.7 C": "Successful Cases (Contains O_Accepted)",
    "11.7 D": "Unsuccessful Cases (Contains O_Refused)",
    "11.7 E": "Canceled Cases (Last Event O_Cancelled)",
}

RULES = {
    "11.7 A": "Hitung seluruh case/trace unik pada event log aktif.",
    "11.7 B": (
        "Rata-rata cycle time (timestamp event terakhir - event pertama, dalam hari) "
        "dari seluruh case, tanpa menghapus event."
    ),
    "11.7 C": (
        "Case yang mengandung minimal satu event dengan concept:name == 'O_Accepted' "
        "(dihitung 1 kali per case)."
    ),
    "11.7 D": (
        "Case yang mengandung minimal satu event dengan concept:name == 'O_Refused' "
        "(dihitung 1 kali per case; boleh tumpang tindih dengan 11.7 C)."
    ),
    "11.7 E": (
        "Case yang event terakhirnya pada trace terurut (timestamp, lalu urutan asli) "
        "adalah 'O_Cancelled'. Case yang hanya pernah memuat O_Cancelled di tengah "
        "tidak dihitung."
    ),
}

RULE_SUMMARY = (
    "Exercise 11.7 A-E: A=total unique cases; B=mean cycle time (days) all cases; "
    "C=contains O_Accepted; D=contains O_Refused; "
    "E=last event in ordered trace is O_Cancelled."
)


def _empty_result() -> dict[str, Any]:
    details = [
        {
            "code": code,
            "title": TITLES[code],
            "rule": RULES[code],
            "total_cases": 0,
            "mean_cycle_time_days": 0.0,
            "case_ids": [],
            "case_evidence": [],
        }
        for code in SUBQUESTIONS
    ]
    return {
        "exercise": "11.7",
        "rule": RULE_SUMMARY,
        "total_cases": 0,
        "mean_cycle_time_days": 0.0,
        "case_ids": [],
        "details": details,
    }


def _order_events(event_df: pd.DataFrame) -> pd.DataFrame:
    """Salin kolom yang dibutuhkan, normalkan tipe, lalu urutkan trace secara deterministik."""
    df = event_df[list(REQUIRED_COLUMNS)].copy()
    df[CASE_COL] = df[CASE_COL].astype(str)
    df[ACT_COL] = df[ACT_COL].astype(str)
    # utc=True agar campuran timezone tetap bisa dibandingkan.
    df[TS_COL] = pd.to_datetime(df[TS_COL], utc=True, errors="raise")
    # _orig_order = tie-breaker untuk timestamp yang sama (urutan asli di log).
    df["_orig_order"] = range(len(df))
    df = df.sort_values([CASE_COL, TS_COL, "_orig_order"]).reset_index(drop=True)
    df["_pos"] = df.groupby(CASE_COL, sort=False).cumcount()
    return df


def _case_table(df: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per case: waktu awal/akhir, jumlah event, aktivitas terakhir, cycle time."""
    grouped = df.groupby(CASE_COL, sort=False)
    cases = grouped.agg(
        first_ts=(TS_COL, "min"),
        last_ts=(TS_COL, "max"),
        n_events=(ACT_COL, "size"),
        last_activity=(ACT_COL, "last"),  # df sudah terurut -> event terakhir trace
    )
    cases["cycle_days"] = (cases["last_ts"] - cases["first_ts"]).dt.total_seconds() / SECONDS_PER_DAY
    cases["first_iso"] = cases["first_ts"].map(lambda t: t.isoformat())
    cases["last_iso"] = cases["last_ts"].map(lambda t: t.isoformat())
    return cases


def _events_for(df: pd.DataFrame, activity: str) -> dict[str, list[dict[str, Any]]]:
    """Event bukti per case untuk satu nama aktivitas (hanya baris yang cocok)."""
    sub = df[df[ACT_COL] == activity]
    out: dict[str, list[dict[str, Any]]] = {}
    for cid, ts, pos in zip(sub[CASE_COL], sub[TS_COL], sub["_pos"]):
        out.setdefault(cid, []).append(
            {"activity": activity, "timestamp": ts.isoformat(), "index": int(pos)}
        )
    return out


def _detail(
    code: str,
    case_ids: list[str],
    info: dict[str, dict[str, Any]],
    mean_days: float,
    events_map: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    rows = []
    for cid in case_ids:
        i = info[cid]
        events = events_map.get(cid, []) if events_map is not None else []
        rows.append(
            {
                "case_id": cid,
                "cycle_time_days": float(i["cycle_days"]),
                "matched_count": len(events) if events_map is not None else 1,
                "n_events": int(i["n_events"]),
                "last_activity": i["last_activity"],
                "first_timestamp": i["first_iso"],
                "last_timestamp": i["last_iso"],
                "evidence_events": events,
            }
        )
    return {
        "code": code,
        "title": TITLES[code],
        "rule": RULES[code],
        "total_cases": len(case_ids),
        "mean_cycle_time_days": mean_days,
        "case_ids": case_ids,
        "case_evidence": rows,
    }


def _mean(series: pd.Series) -> float:
    return float(series.mean()) if len(series) else 0.0


def analyze_exercise_117(event_df: pd.DataFrame) -> dict[str, Any]:
    """Hitung jawaban Exercise 11.7 (A-E) dari event_df (level case)."""
    if event_df is None or event_df.empty:
        return _empty_result()

    missing = [col for col in REQUIRED_COLUMNS if col not in event_df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ditemukan pada event_df: {', '.join(missing)}")

    df = _order_events(event_df)
    cases = _case_table(df)
    info = cases[["cycle_days", "n_events", "last_activity", "first_iso", "last_iso"]].to_dict("index")

    all_ids = cases.index.tolist()
    mean_all = _mean(cases["cycle_days"])

    accepted_events = _events_for(df, ACCEPTED)
    refused_events = _events_for(df, REFUSED)

    c_mask = cases.index.isin(list(accepted_events))
    d_mask = cases.index.isin(list(refused_events))
    e_mask = (cases["last_activity"] == CANCELLED).to_numpy()

    c_ids = cases.index[c_mask].tolist()
    d_ids = cases.index[d_mask].tolist()
    e_ids = cases.index[e_mask].tolist()

    # Bukti 11.7 E = event terakhir trace itu sendiri.
    cancelled_last = {
        cid: [
            {
                "activity": CANCELLED,
                "timestamp": info[cid]["last_iso"],
                "index": int(info[cid]["n_events"]) - 1,
            }
        ]
        for cid in e_ids
    }

    details = [
        _detail("11.7 A", all_ids, info, mean_all),
        _detail("11.7 B", all_ids, info, mean_all),
        _detail("11.7 C", c_ids, info, _mean(cases.loc[c_mask, "cycle_days"]), accepted_events),
        _detail("11.7 D", d_ids, info, _mean(cases.loc[d_mask, "cycle_days"]), refused_events),
        _detail("11.7 E", e_ids, info, _mean(cases.loc[e_mask, "cycle_days"]), cancelled_last),
    ]

    return {
        "exercise": "11.7",
        "rule": RULE_SUMMARY,
        "total_cases": len(all_ids),
        "mean_cycle_time_days": mean_all,
        "case_ids": all_ids,
        "details": details,
    }