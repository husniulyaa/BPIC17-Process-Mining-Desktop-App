"""Unit test untuk modul analisis Exercise 11.22 (F06).

Menguji seluruh skenario minimum pada TEAM_BASELINE.md:
- O_Cancelled diikuti O_Accepted langsung maupun dengan event perantara.
- O_Cancelled tanpa O_Accepted.
- O_Accepted sebelum O_Cancelled.
- Timestamp terurut, acak/tidak terurut, mixed timezone, sama persis, dan NaT.
- Case satu event, event berulang, dataset kosong, None, dan atribut hilang.
- Keutuhan DataFrame masukan dan keberadaan atribut opsional.
"""

from __future__ import annotations

import unittest

import pandas as pd

from analysis.exercise_1122 import (
    ACCEPTED_ACTIVITY,
    CANCELLED_ACTIVITY,
    EXERCISE_1122_ID,
    LIFECYCLE_ATTRIBUTE,
    RESOURCE_ATTRIBUTE,
    analyze_exercise_1122,
)
from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    REQUIRED_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
)


def _event(
    case_id: str | None,
    activity: str | None,
    timestamp: str | None,
    lifecycle: str | None = None,
    resource: str | None = None,
    include_optional: bool = False,
) -> dict:
    row = {
        CASE_ID_ATTRIBUTE: case_id,
        ACTIVITY_ATTRIBUTE: activity,
        TIMESTAMP_ATTRIBUTE: timestamp,
    }
    if include_optional or lifecycle is not None:
        row[LIFECYCLE_ATTRIBUTE] = lifecycle
    if include_optional or resource is not None:
        row[RESOURCE_ATTRIBUTE] = resource
    return row


class Exercise1122AnalysisTests(unittest.TestCase):
    def _build_manual_fixture(self) -> pd.DataFrame:
        """Fixture kecil yang seluruh jawabannya dapat dihitung secara manual."""
        return pd.DataFrame(
            [
                # CASE_ADJ: O_Cancelled langsung diikuti O_Accepted (1 jam kemudian) -> COCOK
                _event("CASE_ADJ", "A_Create Application", "2026-01-01T08:00:00Z"),
                _event("CASE_ADJ", CANCELLED_ACTIVITY, "2026-01-01T09:00:00Z"),
                _event("CASE_ADJ", ACCEPTED_ACTIVITY, "2026-01-01T10:00:00Z"),
                # CASE_GAP: O_Cancelled lalu 2 event perantara lalu O_Accepted (2 hari) -> COCOK
                _event("CASE_GAP", "A_Create Application", "2026-01-01T00:00:00Z"),
                _event("CASE_GAP", CANCELLED_ACTIVITY, "2026-01-02T00:00:00Z"),
                _event("CASE_GAP", "W_Call after offers", "2026-01-02T12:00:00Z"),
                _event("CASE_GAP", "O_Sent (mail and online)", "2026-01-03T00:00:00Z"),
                _event("CASE_GAP", ACCEPTED_ACTIVITY, "2026-01-04T00:00:00Z"),
                # CASE_ONLY_CANCEL: O_Cancelled tanpa O_Accepted -> TIDAK COCOK
                _event("CASE_ONLY_CANCEL", "A_Create Application", "2026-01-01T00:00:00Z"),
                _event("CASE_ONLY_CANCEL", CANCELLED_ACTIVITY, "2026-01-02T00:00:00Z"),
                # CASE_ONLY_ACCEPT: O_Accepted tanpa O_Cancelled -> TIDAK COCOK
                _event("CASE_ONLY_ACCEPT", "A_Create Application", "2026-01-01T00:00:00Z"),
                _event("CASE_ONLY_ACCEPT", ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
                # CASE_REVERSE: O_Accepted SEBELUM O_Cancelled -> TIDAK COCOK
                _event("CASE_REVERSE", "A_Create Application", "2026-01-01T00:00:00Z"),
                _event("CASE_REVERSE", ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
                _event("CASE_REVERSE", CANCELLED_ACTIVITY, "2026-01-03T00:00:00Z"),
                # CASE_SINGLE: satu event saja -> TIDAK COCOK
                _event("CASE_SINGLE", CANCELLED_ACTIVITY, "2026-01-01T00:00:00Z"),
            ]
        )

    def test_manual_fixture_matches_expected_cases_and_evidence(self) -> None:
        df = self._build_manual_fixture()
        result = analyze_exercise_1122(df)

        self.assertEqual(result["exercise"], EXERCISE_1122_ID)
        self.assertIsInstance(result["rule"], str)
        self.assertEqual(result["total_cases_in_log"], 6)
        self.assertEqual(result["total_cases"], 2)
        self.assertEqual(result["case_ids"], ["CASE_ADJ", "CASE_GAP"])
        self.assertEqual(result["same_timestamp_cases"], [])

        details_by_id = {d["case_id"]: d for d in result["details"]}

        adj = details_by_id["CASE_ADJ"]
        self.assertEqual(adj["events_between_count"], 0)
        self.assertAlmostEqual(adj["time_between_seconds"], 3600.0)
        self.assertEqual(adj["time_between_display"], "01:00:00")
        self.assertEqual(adj["first_cancelled_index"], 1)
        self.assertEqual(adj["first_accepted_after_cancelled_index"], 2)
        self.assertEqual(len(adj["timeline_excerpt"]), 2)

        gap = details_by_id["CASE_GAP"]
        self.assertEqual(gap["events_between_count"], 2)
        self.assertAlmostEqual(gap["time_between_days"], 2.0)
        self.assertEqual(gap["time_between_display"], "2d 00:00:00")
        self.assertEqual(gap["total_events"], 5)
        self.assertEqual(
            [e["activity"] for e in gap["timeline_excerpt"]],
            [
                CANCELLED_ACTIVITY,
                "W_Call after offers",
                "O_Sent (mail and online)",
                ACCEPTED_ACTIVITY,
            ],
        )

    def test_unsorted_rows_produce_identical_results(self) -> None:
        df = self._build_manual_fixture()
        expected = analyze_exercise_1122(df)

        shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)
        actual = analyze_exercise_1122(shuffled)

        self.assertEqual(actual["case_ids"], expected["case_ids"])
        self.assertEqual(actual["total_cases"], expected["total_cases"])
        self.assertEqual(actual["details"], expected["details"])

    def test_repeated_targets_count_case_once_and_pick_post_cancel_accept(self) -> None:
        df = pd.DataFrame(
            [
                # O_Accepted (hari 1) -> O_Cancelled (hari 2) -> O_Cancelled (hari 3) -> O_Accepted (hari 4) -> O_Accepted (hari 5)
                _event("CASE_REP", ACCEPTED_ACTIVITY, "2026-01-01T00:00:00Z"),
                _event("CASE_REP", CANCELLED_ACTIVITY, "2026-01-02T00:00:00Z"),
                _event("CASE_REP", CANCELLED_ACTIVITY, "2026-01-03T00:00:00Z"),
                _event("CASE_REP", ACCEPTED_ACTIVITY, "2026-01-04T00:00:00Z"),
                _event("CASE_REP", ACCEPTED_ACTIVITY, "2026-01-05T00:00:00Z"),
            ]
        )

        result = analyze_exercise_1122(df)
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["case_ids"], ["CASE_REP"])

        detail = result["details"][0]
        self.assertEqual(detail["cancelled_count"], 2)
        self.assertEqual(detail["accepted_count"], 3)
        self.assertEqual(detail["accepted_after_cancelled_count"], 2)
        self.assertEqual(detail["first_cancelled_timestamp"], "2026-01-02T00:00:00+00:00")
        self.assertEqual(
            detail["first_accepted_after_cancelled_timestamp"],
            "2026-01-04T00:00:00+00:00",
        )
        self.assertEqual(
            detail["last_accepted_after_cancelled_timestamp"],
            "2026-01-05T00:00:00+00:00",
        )
        self.assertAlmostEqual(detail["time_between_days"], 2.0)

    def test_equal_timestamp_tie_is_not_assumed_ordered_and_is_documented(self) -> None:
        df = pd.DataFrame(
            [
                # CASE_TIE: O_Cancelled & O_Accepted pada timestamp sama persis -> TIDAK dihitung
                _event("CASE_TIE", CANCELLED_ACTIVITY, "2026-01-02T10:00:00Z"),
                _event("CASE_TIE", ACCEPTED_ACTIVITY, "2026-01-02T10:00:00Z"),
                # CASE_TIE_THEN_LATER: ada tie di 10:00, tapi ada O_Accepted lagi di 11:00 -> COCOK
                _event("CASE_TIE_THEN_LATER", CANCELLED_ACTIVITY, "2026-01-02T10:00:00Z"),
                _event("CASE_TIE_THEN_LATER", ACCEPTED_ACTIVITY, "2026-01-02T10:00:00Z"),
                _event("CASE_TIE_THEN_LATER", ACCEPTED_ACTIVITY, "2026-01-02T11:00:00Z"),
            ]
        )

        result = analyze_exercise_1122(df)
        self.assertEqual(result["case_ids"], ["CASE_TIE_THEN_LATER"])
        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["same_timestamp_cases"], ["CASE_TIE"])
        self.assertTrue(any("timestamp persis sama" in w for w in result["warnings"]))
        self.assertEqual(
            result["details"][0]["first_accepted_after_cancelled_timestamp"],
            "2026-01-02T11:00:00+00:00",
        )

    def test_mixed_timezones_are_compared_in_utc(self) -> None:
        df = pd.DataFrame(
            [
                # 10:00+02:00 == 08:00Z (lebih awal)
                _event("CASE_TZ_OK", CANCELLED_ACTIVITY, "2026-01-01T10:00:00+02:00"),
                # 09:00+00:00 == 09:00Z (1 jam lebih akhir)
                _event("CASE_TZ_OK", ACCEPTED_ACTIVITY, "2026-01-01T09:00:00+00:00"),
                # 12:00+02:00 == 10:00Z (lebih akhir), 09:30Z lebih awal -> TIDAK cocok
                _event("CASE_TZ_REV", CANCELLED_ACTIVITY, "2026-01-01T12:00:00+02:00"),
                _event("CASE_TZ_REV", ACCEPTED_ACTIVITY, "2026-01-01T09:30:00+00:00"),
            ]
        )

        result = analyze_exercise_1122(df)
        self.assertEqual(result["case_ids"], ["CASE_TZ_OK"])
        self.assertAlmostEqual(result["details"][0]["time_between_seconds"], 3600.0)

    def test_invalid_nat_timestamps_do_not_produce_false_match(self) -> None:
        df = pd.DataFrame(
            [
                _event("CASE_NAT", CANCELLED_ACTIVITY, "not-a-date"),
                _event("CASE_NAT", ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
            ]
        )

        result = analyze_exercise_1122(df)
        self.assertEqual(result["total_cases"], 0)
        self.assertEqual(result["case_ids"], [])
        self.assertTrue(any("NaT" in w for w in result["warnings"]))

    def test_optional_columns_included_only_when_present_without_fabrication(self) -> None:
        # Tanpa kolom opsional
        df_min = pd.DataFrame(
            [
                _event("C1", CANCELLED_ACTIVITY, "2026-01-01T00:00:00Z"),
                _event("C1", ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
            ]
        )
        res_min = analyze_exercise_1122(df_min)
        ev_min = res_min["details"][0]["evidence_events"][0]
        self.assertNotIn(LIFECYCLE_ATTRIBUTE, ev_min)
        self.assertNotIn(RESOURCE_ATTRIBUTE, ev_min)

        # Dengan kolom opsional (termasuk nilai kosong)
        df_opt = pd.DataFrame(
            [
                _event(
                    "C1",
                    CANCELLED_ACTIVITY,
                    "2026-01-01T00:00:00Z",
                    lifecycle="complete",
                    resource=None,
                    include_optional=True,
                ),
                _event(
                    "C1",
                    ACCEPTED_ACTIVITY,
                    "2026-01-02T00:00:00Z",
                    lifecycle="complete",
                    resource="User_1",
                    include_optional=True,
                ),
            ]
        )
        res_opt = analyze_exercise_1122(df_opt)
        ev0, ev1 = res_opt["details"][0]["evidence_events"]
        self.assertEqual(ev0[LIFECYCLE_ATTRIBUTE], "complete")
        self.assertIsNone(ev0[RESOURCE_ATTRIBUTE])
        self.assertEqual(ev1[RESOURCE_ATTRIBUTE], "User_1")

    def test_empty_and_none_inputs_return_empty_structure(self) -> None:
        for data in (None, pd.DataFrame(columns=list(REQUIRED_ATTRIBUTES))):
            result = analyze_exercise_1122(data)
            self.assertEqual(result["exercise"], EXERCISE_1122_ID)
            self.assertEqual(result["total_cases"], 0)
            self.assertEqual(result["total_cases_in_log"], 0)
            self.assertEqual(result["case_ids"], [])
            self.assertEqual(result["details"], [])

    def test_missing_required_column_raises_value_error(self) -> None:
        df = self._build_manual_fixture().drop(columns=[TIMESTAMP_ATTRIBUTE])
        with self.assertRaisesRegex(ValueError, TIMESTAMP_ATTRIBUTE):
            analyze_exercise_1122(df)

    def test_non_dataframe_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            analyze_exercise_1122([{"case": "1"}])  # type: ignore[arg-type]

    def test_missing_case_id_rows_are_ignored_with_warning(self) -> None:
        df = pd.DataFrame(
            [
                _event(None, CANCELLED_ACTIVITY, "2026-01-01T00:00:00Z"),
                _event(None, ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
                _event("VALID", CANCELLED_ACTIVITY, "2026-01-01T00:00:00Z"),
                _event("VALID", ACCEPTED_ACTIVITY, "2026-01-02T00:00:00Z"),
            ]
        )
        result = analyze_exercise_1122(df)
        self.assertEqual(result["case_ids"], ["VALID"])
        self.assertEqual(result["total_cases_in_log"], 1)
        self.assertTrue(any(CASE_ID_ATTRIBUTE in w for w in result["warnings"]))

    def test_input_dataframe_is_not_mutated(self) -> None:
        df = self._build_manual_fixture()
        before = df.copy(deep=True)
        analyze_exercise_1122(df)
        pd.testing.assert_frame_equal(df, before)


if __name__ == "__main__":
    unittest.main()
