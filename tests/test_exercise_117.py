import pandas as pd
import pytest

from analysis.exercise_117 import REQUIRED_COLUMNS, analyze_exercise_117

CASE, ACT, TS = REQUIRED_COLUMNS
CODES = ["11.7 A", "11.7 B", "11.7 C", "11.7 D", "11.7 E"]


def _row(case, activity, ts):
    return {CASE: case, ACT: activity, TS: ts}


def _by_code(result):
    """details berupa list; ubah jadi dict {code: elemen} agar mudah dicek di tes."""
    return {item["code"]: item for item in result["details"]}


@pytest.fixture
def manual_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # CASE_A: O_Accepted 2x (harus terhitung 1 case); durasi 2.0 hari
            _row("CASE_A", "A_Create Application", "2026-01-01 00:00:00"),
            _row("CASE_A", "O_Accepted", "2026-01-02 00:00:00"),
            _row("CASE_A", "O_Accepted", "2026-01-03 00:00:00"),
            # CASE_B: O_Cancelled di tengah, lanjut event lain; durasi 1.0 hari
            _row("CASE_B", "A_Create Application", "2026-01-01 00:00:00"),
            _row("CASE_B", "O_Cancelled", "2026-01-01 12:00:00"),
            _row("CASE_B", "A_Pending", "2026-01-02 00:00:00"),
            # CASE_C: O_Refused dan O_Accepted sekaligus; durasi 3.0 hari
            _row("CASE_C", "A_Create Application", "2026-01-01 00:00:00"),
            _row("CASE_C", "O_Refused", "2026-01-02 00:00:00"),
            _row("CASE_C", "O_Accepted", "2026-01-04 00:00:00"),
            # CASE_D: berakhir O_Cancelled; durasi 4.0 hari
            _row("CASE_D", "A_Create Application", "2026-01-01 00:00:00"),
            _row("CASE_D", "O_Cancelled", "2026-01-05 00:00:00"),
        ]
    )


def test_details_is_list_in_a_to_e_order(manual_df):
    result = analyze_exercise_117(manual_df)
    assert isinstance(result["details"], list)
    assert [item["code"] for item in result["details"]] == CODES


def test_manual_calculations(manual_df):
    result = analyze_exercise_117(manual_df)
    d = _by_code(result)

    assert result["exercise"] == "11.7"
    assert result["total_cases"] == 4
    # (2 + 1 + 3 + 4) / 4 = 2.5 hari
    assert result["mean_cycle_time_days"] == pytest.approx(2.5)

    assert d["11.7 A"]["total_cases"] == 4
    assert d["11.7 B"]["mean_cycle_time_days"] == pytest.approx(2.5)

    # C: CASE_A (2x accepted tetap 1 case) dan CASE_C -> (2 + 3) / 2
    assert d["11.7 C"]["total_cases"] == 2
    assert d["11.7 C"]["case_ids"] == ["CASE_A", "CASE_C"]
    assert d["11.7 C"]["mean_cycle_time_days"] == pytest.approx(2.5)

    # D: hanya CASE_C (tumpang tindih dengan C itu boleh)
    assert d["11.7 D"]["case_ids"] == ["CASE_C"]
    assert d["11.7 D"]["mean_cycle_time_days"] == pytest.approx(3.0)

    # E: hanya CASE_D; CASE_B punya O_Cancelled di tengah sehingga tidak dihitung
    assert d["11.7 E"]["case_ids"] == ["CASE_D"]
    assert d["11.7 E"]["mean_cycle_time_days"] == pytest.approx(4.0)


def test_case_counted_once_with_evidence(manual_df):
    c = _by_code(analyze_exercise_117(manual_df))["11.7 C"]
    row = next(r for r in c["case_evidence"] if r["case_id"] == "CASE_A")
    assert row["matched_count"] == 2
    assert [e["index"] for e in row["evidence_events"]] == [1, 2]
    assert row["cycle_time_days"] == pytest.approx(2.0)


def test_single_event_case_has_zero_cycle_time():
    df = pd.DataFrame(
        [
            _row("ONE", "O_Cancelled", "2026-03-01 09:00:00"),
            _row("TWO", "A_Create Application", "2026-03-01 09:00:00"),
            _row("TWO", "O_Accepted", "2026-03-03 09:00:00"),
        ]
    )
    d = _by_code(analyze_exercise_117(df))
    assert d["11.7 A"]["total_cases"] == 2
    # Satu event -> awal = akhir -> 0 hari; juga event terakhir = O_Cancelled
    assert d["11.7 E"]["case_ids"] == ["ONE"]
    assert d["11.7 E"]["mean_cycle_time_days"] == pytest.approx(0.0)
    # (0 + 2) / 2 = 1.0 hari
    assert d["11.7 B"]["mean_cycle_time_days"] == pytest.approx(1.0)


def test_row_order_does_not_matter(manual_df):
    expected = _by_code(analyze_exercise_117(manual_df))
    shuffled = manual_df.sample(frac=1, random_state=0).reset_index(drop=True)
    got = _by_code(analyze_exercise_117(shuffled))
    for code in CODES:
        assert got[code]["case_ids"] == expected[code]["case_ids"]
        assert got[code]["mean_cycle_time_days"] == pytest.approx(
            expected[code]["mean_cycle_time_days"]
        )


def test_equal_timestamps_follow_original_order():
    # O_Cancelled lalu O_Accepted pada timestamp sama -> event terakhir O_Accepted
    cancelled_first = pd.DataFrame(
        [
            _row("T1", "A_Create Application", "2026-02-01 08:00:00"),
            _row("T1", "O_Cancelled", "2026-02-02 08:00:00"),
            _row("T1", "O_Accepted", "2026-02-02 08:00:00"),
        ]
    )
    assert _by_code(analyze_exercise_117(cancelled_first))["11.7 E"]["case_ids"] == []

    # Kebalikannya -> event terakhir O_Cancelled
    accepted_first = pd.DataFrame(
        [
            _row("T2", "A_Create Application", "2026-02-01 08:00:00"),
            _row("T2", "O_Accepted", "2026-02-02 08:00:00"),
            _row("T2", "O_Cancelled", "2026-02-02 08:00:00"),
        ]
    )
    d = _by_code(analyze_exercise_117(accepted_first))
    assert d["11.7 E"]["case_ids"] == ["T2"]
    assert d["11.7 C"]["case_ids"] == ["T2"]


def test_mixed_timezones_are_comparable():
    df = pd.DataFrame(
        [
            _row("TZ", "A_Create Application", "2026-01-01 10:00:00+01:00"),  # 09:00 UTC
            _row("TZ", "O_Accepted", "2026-01-02 09:00:00+00:00"),
        ]
    )
    result = analyze_exercise_117(df)
    assert result["mean_cycle_time_days"] == pytest.approx(1.0)


def test_empty_and_none_input():
    for empty in (None, pd.DataFrame(columns=list(REQUIRED_COLUMNS))):
        result = analyze_exercise_117(empty)
        assert result["total_cases"] == 0
        assert result["mean_cycle_time_days"] == 0.0
        assert [item["code"] for item in result["details"]] == CODES


def test_missing_required_column_raises(manual_df):
    with pytest.raises(ValueError, match="time:timestamp"):
        analyze_exercise_117(manual_df.drop(columns=[TS]))


def test_input_dataframe_is_not_modified(manual_df):
    before = manual_df.copy(deep=True)
    analyze_exercise_117(manual_df)
    pd.testing.assert_frame_equal(manual_df, before)