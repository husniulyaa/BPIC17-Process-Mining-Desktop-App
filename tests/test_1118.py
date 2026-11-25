"""Pengujian unit dan integrasi untuk Exercise 11.18."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from analysis.exercise_1115 import analyze_exercise_1115
from analysis.exercise_1118 import analyze_exercise_1118

EXPECTED_KEYS = {
    "exercise",
    "rule",
    "total_cases",
    "case_ids",
    "details",
    "total_cases_in_log",
    "denominator_note",
    "warnings",
}


def _make_df(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_two_complete_different_resources_not_qualified_1118() -> None:
    """2 complete oleh resource berbeda lolos 11.15 tetapi TIDAK lolos 11.18."""
    df = _make_df(
        [
            {
                "case:concept:name": "C1",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "C1",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_2",
            },
        ]
    )
    res_1115 = analyze_exercise_1115(df)
    res_1118 = analyze_exercise_1118(df)
    assert res_1115["total_cases"] == 1
    assert res_1118["total_cases"] == 0
    assert res_1118["case_ids"] == []


def test_two_complete_same_resource_qualifies_1118() -> None:
    """2 complete oleh resource sama lolos 11.15 dan 11.18."""
    df = _make_df(
        [
            {
                "case:concept:name": "C2",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_10",
            },
            {
                "case:concept:name": "C2",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_10",
            },
        ]
    )
    res = analyze_exercise_1118(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C2"]
    assert res["details"][0]["resource"] == "User_10"
    assert res["details"][0]["complete_count_by_resource"] == 2


def test_three_complete_two_by_a_one_by_b() -> None:
    """3 complete (2 oleh A, 1 oleh B) lolos 11.18 dengan resource A, count = 2."""
    df = _make_df(
        [
            {
                "case:concept:name": "C3",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_A",
            },
            {
                "case:concept:name": "C3",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_B",
            },
            {
                "case:concept:name": "C3",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T12:00:00+00:00",
                "org:resource": "User_A",
            },
        ]
    )
    res = analyze_exercise_1118(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C3"]
    assert len(res["details"]) == 1
    assert res["details"][0]["resource"] == "User_A"
    assert res["details"][0]["complete_count_by_resource"] == 2
    assert len(res["details"][0]["evidence"]) == 2


def test_empty_or_nan_resource_not_grouped_and_emits_warning() -> None:
    """Resource kosong/NaN/whitespace pada 2 complete tidak lolos 11.18 dan memberi warning."""
    df = _make_df(
        [
            {
                "case:concept:name": "C4",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": None,
            },
            {
                "case:concept:name": "C4",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "   ",
            },
            {
                "case:concept:name": "C4",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T12:00:00+00:00",
                "org:resource": float("nan"),
            },
        ]
    )
    res = analyze_exercise_1118(df)
    assert res["total_cases"] == 0
    assert res["case_ids"] == []
    assert any("org:resource kosong/NaN" in w for w in res["warnings"])


def test_schedule_ignored_for_same_resource() -> None:
    """Schedule oleh resource sama tidak dihitung untuk 11.18."""
    df = _make_df(
        [
            {
                "case:concept:name": "C5",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "schedule",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "C5",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_1",
            },
        ]
    )
    res = analyze_exercise_1118(df)
    assert res["total_cases"] == 0


def test_missing_lifecycle_or_resource_column_no_crash() -> None:
    """Kolom lifecycle atau org:resource tidak ada -> tidak crash dan ada warning."""
    df_no_lifecycle = _make_df(
        [
            {
                "case:concept:name": "C6",
                "concept:name": "W_Assess potential fraud",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
            },
        ]
    )
    res_no_lc = analyze_exercise_1118(df_no_lifecycle)
    assert res_no_lc["total_cases"] == 0
    assert len(res_no_lc["warnings"]) >= 1

    df_no_res = _make_df(
        [
            {
                "case:concept:name": "C6",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
            },
        ]
    )
    res_no_res = analyze_exercise_1118(df_no_res)
    assert res_no_res["total_cases"] == 0
    assert any("org:resource" in w for w in res_no_res["warnings"])


def test_input_dataframe_not_mutated_and_contract_keys_present() -> None:
    """DataFrame masukan tidak termodifikasi dan seluruh key kontrak tersedia."""
    df = _make_df(
        [
            {
                "case:concept:name": "C7",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_X",
                "EventID": "EV1",
            },
            {
                "case:concept:name": "C7",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_X",
                "EventID": "EV2",
            },
        ]
    )
    df_before = df.copy(deep=True)
    res = analyze_exercise_1118(df)

    pd.testing.assert_frame_equal(df, df_before)
    assert EXPECTED_KEYS.issubset(res.keys())
    assert res["exercise"] == "11.18"
    assert res["details"][0]["evidence"][0]["EventID"] == "EV1"


_CSV_PATH = os.environ.get("BPIC17_CSV_PATH", "")


@pytest.mark.skipif(
    not _CSV_PATH or not Path(_CSV_PATH).is_file(),
    reason="BPIC17_CSV_PATH tidak disetel atau file CSV lokal tidak ditemukan.",
)
def test_integration_bpic17_csv_1118() -> None:
    """Verifikasi terhadap dataset BPIC17 CSV lokal dan relasi subset terhadap 11.15."""
    df = pd.read_csv(_CSV_PATH)
    res_1115 = analyze_exercise_1115(df)
    res_1118 = analyze_exercise_1118(df)
    assert res_1118["total_cases"] == 3
    assert set(res_1118["case_ids"]).issubset(set(res_1115["case_ids"]))
