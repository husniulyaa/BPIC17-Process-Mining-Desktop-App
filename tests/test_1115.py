"""Pengujian unit dan integrasi untuk Exercise 11.15."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from analysis.exercise_1115 import analyze_exercise_1115

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


def test_schedule_twice_complete_once_not_qualified() -> None:
    """Aktivitas schedule 2x tetapi complete hanya 1x tidak lolos 11.15."""
    df = _make_df(
        [
            {
                "case:concept:name": "C1",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "schedule",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "C1",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "schedule",
                "time:timestamp": "2016-01-01T10:05:00+00:00",
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "C1",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:10:00+00:00",
                "org:resource": "User_1",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 0
    assert res["case_ids"] == []
    assert res["total_cases_in_log"] == 1


def test_two_complete_different_resources_qualifies_1115() -> None:
    """2 complete oleh resource berbeda tetap lolos 11.15."""
    df = _make_df(
        [
            {
                "case:concept:name": "C2",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
            },
            {
                "case:concept:name": "C2",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_2",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C2"]
    assert res["details"][0]["complete_count"] == 2


def test_two_complete_same_resource_qualifies_1115() -> None:
    """2 complete oleh resource sama lolos 11.15."""
    df = _make_df(
        [
            {
                "case:concept:name": "C3",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
                "EventID": "E1",
            },
            {
                "case:concept:name": "C3",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:30:00+00:00",
                "org:resource": "User_1",
                "EventID": "E2",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C3"]
    assert len(res["details"][0]["evidence"]) == 2
    assert res["details"][0]["evidence"][0]["EventID"] == "E1"


def test_activity_case_insensitive_and_whitespace() -> None:
    """Pencocokan aktivitas dan lifecycle bersifat case-insensitive dan strip whitespace."""
    df = _make_df(
        [
            {
                "case:concept:name": "C4",
                "concept:name": "  W_Assess Potential Fraud ",
                "lifecycle:transition": "COMPLETE",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
            },
            {
                "case:concept:name": "C4",
                "concept:name": "w_assess potential fraud",
                "lifecycle:transition": " Complete ",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C4"]


def test_non_target_cases_excluded_and_multiple_occurrences_counted_once() -> None:
    """Case tanpa aktivitas target tidak ikut; banyak occurrence dihitung satu case."""
    df = _make_df(
        [
            {
                "case:concept:name": "C_OTHER",
                "concept:name": "A_Create Application",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T09:00:00+00:00",
            },
            {
                "case:concept:name": "C_MULTI",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
            },
            {
                "case:concept:name": "C_MULTI",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
            },
            {
                "case:concept:name": "C_MULTI",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T12:00:00+00:00",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 1
    assert res["case_ids"] == ["C_MULTI"]
    assert res["details"][0]["complete_count"] == 3
    assert res["total_cases_in_log"] == 2


def test_missing_lifecycle_column_returns_warning_without_crash() -> None:
    """Jika kolom lifecycle:transition tidak ada, tidak crash dan mengembalikan warning."""
    df = _make_df(
        [
            {
                "case:concept:name": "C5",
                "concept:name": "W_Assess potential fraud",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
            },
            {
                "case:concept:name": "C5",
                "concept:name": "W_Assess potential fraud",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
            },
        ]
    )
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 0
    assert res["case_ids"] == []
    assert res["total_cases_in_log"] == 1
    assert len(res["warnings"]) >= 1
    assert "lifecycle:transition" in res["warnings"][0]


def test_input_dataframe_not_mutated_and_contract_keys_present() -> None:
    """DataFrame masukan tidak termodifikasi dan seluruh key kontrak tersedia."""
    df = _make_df(
        [
            {
                "case:concept:name": "C6",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T12:00:00+00:00",
                "extra_col": "keep_me",
            },
            {
                "case:concept:name": "C6",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "extra_col": "keep_me_2",
            },
        ]
    )
    df_before = df.copy(deep=True)
    res = analyze_exercise_1115(df)

    pd.testing.assert_frame_equal(df, df_before)
    assert EXPECTED_KEYS.issubset(res.keys())
    assert res["exercise"] == "11.15"
    assert isinstance(res["case_ids"], list)
    assert isinstance(res["details"], list)
    assert res["details"][0]["evidence"][0]["timestamp"] <= res["details"][0]["evidence"][1]["timestamp"]


_CSV_PATH = os.environ.get("BPIC17_CSV_PATH", "")


@pytest.mark.skipif(
    not _CSV_PATH or not Path(_CSV_PATH).is_file(),
    reason="BPIC17_CSV_PATH tidak disetel atau file CSV lokal tidak ditemukan.",
)
def test_integration_bpic17_csv_1115() -> None:
    """Verifikasi terhadap dataset BPIC17 CSV lokal."""
    df = pd.read_csv(_CSV_PATH)
    res = analyze_exercise_1115(df)
    assert res["total_cases"] == 13
