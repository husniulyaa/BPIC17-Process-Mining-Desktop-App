"""Tests for dataset overview calculations."""

from __future__ import annotations

import unittest

try:
    import pandas as pd
    from ui.pages.overview_page import calculate_case_durations
except ImportError:
    pd = None
    calculate_case_durations = None


@unittest.skipIf(
    pd is None,
    "Pandas and PySide6 are required for overview calculations.",
)
class OverviewCalculationTests(unittest.TestCase):
    def test_case_cycle_time_uses_full_case_timestamp_range(self) -> None:
        event_df = pd.DataFrame(
            {
                "case:concept:name": ["case-1", "case-2", "case-1", "case-2"],
                "concept:name": ["A", "A", "B", "B"],
                "time:timestamp": [
                    "2020-01-01T00:00:00Z",
                    "invalid",
                    "2020-01-01T02:30:00Z",
                    "2020-01-02T00:00:00Z",
                ],
            }
        )

        durations = calculate_case_durations(event_df).set_index("case:concept:name")

        self.assertEqual(
            durations.loc["case-1", "cycle_time"],
            pd.Timedelta(hours=2, minutes=30),
        )
        self.assertTrue(pd.isna(durations.loc["case-2", "cycle_time"]))
        self.assertEqual(len(durations), 2)

    def test_cycle_time_calculation_does_not_mutate_input(self) -> None:
        event_df = pd.DataFrame(
            {
                "case:concept:name": ["case-1", "case-1"],
                "concept:name": ["A", "B"],
                "time:timestamp": [
                    "2020-01-01T00:00:00Z",
                    "2020-01-01T01:00:00Z",
                ],
            }
        )
        original_columns = event_df.columns.tolist()

        calculate_case_durations(event_df)

        self.assertEqual(event_df.columns.tolist(), original_columns)


if __name__ == "__main__":
    unittest.main()
