"""Tests for XES attribute validation and dataset loading."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    REQUIRED_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)
from core.dataset_loader import DatasetMetadata, load_xes

try:
    import pandas as pd
except ImportError:
    pd = None

HAS_XES_DEPENDENCIES = (
    pd is not None and importlib.util.find_spec("pm4py") is not None
)


@unittest.skipIf(pd is None, "Pandas is not installed.")
class DataContractTests(unittest.TestCase):
    def test_valid_dataframe_returns_present_optional_attributes(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-1"],
                ACTIVITY_ATTRIBUTE: ["Activity A"],
                TIMESTAMP_ATTRIBUTE: ["2020-01-01T00:00:00Z"],
                OPTIONAL_ATTRIBUTES[1]: ["resource-1"],
            }
        )

        self.assertEqual(
            validate_event_dataframe(frame),
            (OPTIONAL_ATTRIBUTES[1],),
        )

    def test_missing_required_attribute_is_reported(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-1"],
                TIMESTAMP_ATTRIBUTE: ["2020-01-01T00:00:00Z"],
            }
        )

        with self.assertRaisesRegex(ValueError, ACTIVITY_ATTRIBUTE):
            validate_event_dataframe(frame)

    def test_empty_dataframe_is_rejected_by_default(self) -> None:
        frame = pd.DataFrame(columns=REQUIRED_ATTRIBUTES)

        with self.assertRaisesRegex(ValueError, "empty"):
            validate_event_dataframe(frame)
        self.assertEqual(validate_event_dataframe(frame, allow_empty=True), ())


@unittest.skipIf(pd is None, "Pandas is not installed.")
class DatasetLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.xes_path = Path(self.temp_directory.name) / "sample.xes"
        self.xes_path.write_text("<log />", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def load_frame(
        self,
        frame: pd.DataFrame,
    ) -> tuple[pd.DataFrame, DatasetMetadata]:
        fake_pm4py = SimpleNamespace(
            read_xes=Mock(return_value=object()),
            convert_to_dataframe=Mock(return_value=frame),
        )
        with patch.dict(sys.modules, {"pm4py": fake_pm4py}):
            return load_xes(self.xes_path)

    def test_load_sorts_cases_and_timestamps_stably_and_keeps_columns(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-b", "case-a", "case-a", "case-a", "case-b"],
                ACTIVITY_ATTRIBUTE: ["B-late", "A-late", "A-first", "A-second", "B-first"],
                TIMESTAMP_ATTRIBUTE: [
                    "2020-01-02T00:00:00Z",
                    "2020-01-02T00:00:00Z",
                    "2020-01-01T00:00:00Z",
                    "2020-01-01T00:00:00Z",
                    "2020-01-01T00:00:00Z",
                ],
                "custom:attribute": [1, 2, 3, 4, 5],
            }
        )

        event_df, metadata = self.load_frame(frame)

        self.assertEqual(
            event_df[ACTIVITY_ATTRIBUTE].tolist(),
            ["A-first", "A-second", "A-late", "B-first", "B-late"],
        )
        self.assertIn("custom:attribute", event_df.columns)
        self.assertTrue(
            pd.api.types.is_datetime64_any_dtype(event_df[TIMESTAMP_ATTRIBUTE])
        )
        self.assertEqual(metadata["case_count"], 2)
        self.assertEqual(metadata["event_count"], 5)
        self.assertEqual(metadata["file_name"], "sample.xes")
        self.assertEqual(metadata["optional_attributes"], [])

    def test_uneven_case_event_counts_are_counted_by_unique_case(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-1", "case-1", "case-2"],
                ACTIVITY_ATTRIBUTE: ["A", "B", "A"],
                TIMESTAMP_ATTRIBUTE: [
                    "2020-01-01T00:00:00Z",
                    "2020-01-01T02:00:00Z",
                    "2020-01-03T00:00:00Z",
                ],
                "org:resource": ["r1", "r2", "r3"],
            }
        )

        event_df, metadata = self.load_frame(frame)

        self.assertEqual(len(event_df), 3)
        self.assertEqual(metadata["case_count"], 2)
        self.assertEqual(metadata["optional_attributes"], ["org:resource"])

    def test_invalid_timestamps_are_coerced_to_nat_and_retained(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-1", "case-1"],
                ACTIVITY_ATTRIBUTE: ["A", "B"],
                TIMESTAMP_ATTRIBUTE: ["not-a-timestamp", "2020-01-01T00:00:00Z"],
            }
        )

        event_df, metadata = self.load_frame(frame)

        self.assertEqual(metadata["event_count"], 2)
        self.assertTrue(pd.isna(event_df[TIMESTAMP_ATTRIBUTE].iloc[-1]))

    def test_pm4py_parser_errors_are_reported_with_file_context(self) -> None:
        fake_pm4py = SimpleNamespace(
            read_xes=Mock(side_effect=ValueError("malformed XML")),
            convert_to_dataframe=Mock(),
        )

        with patch.dict(sys.modules, {"pm4py": fake_pm4py}):
            with self.assertRaisesRegex(ValueError, "sample.xes"):
                load_xes(self.xes_path)

    def test_missing_required_column_is_rejected_by_loader(self) -> None:
        frame = pd.DataFrame(
            {
                CASE_ID_ATTRIBUTE: ["case-1"],
                TIMESTAMP_ATTRIBUTE: ["2020-01-01T00:00:00Z"],
            }
        )

        with patch.dict(
            sys.modules,
            {
                "pm4py": SimpleNamespace(
                    read_xes=Mock(return_value=object()),
                    convert_to_dataframe=Mock(return_value=frame),
                )
            },
        ):
            with self.assertRaisesRegex(ValueError, ACTIVITY_ATTRIBUTE):
                load_xes(self.xes_path)

    @unittest.skipUnless(HAS_XES_DEPENDENCIES, "Pandas and PM4Py are required.")
    def test_reads_a_valid_synthetic_xes_file_when_pm4py_is_available(self) -> None:
        self.xes_path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<log xes.version="1.0" xes.features="nested-attributes"
     xmlns="http://www.xes-standard.org/">
  <trace>
    <string key="concept:name" value="case-1"/>
    <event>
      <string key="concept:name" value="Activity A"/>
      <date key="time:timestamp" value="2020-01-01T00:00:00.000+00:00"/>
    </event>
  </trace>
</log>
""",
            encoding="utf-8",
        )

        event_df, metadata = load_xes(self.xes_path)

        self.assertEqual(metadata["case_count"], 1)
        self.assertEqual(metadata["event_count"], 1)
        self.assertEqual(event_df[ACTIVITY_ATTRIBUTE].tolist(), ["Activity A"])

class DatasetPathValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_missing_file_is_reported_before_dependency_import(self) -> None:
        missing_path = Path(self.temp_directory.name) / "missing.xes"

        with self.assertRaisesRegex(FileNotFoundError, "missing.xes"):
            load_xes(missing_path)

    def test_non_xes_file_is_rejected(self) -> None:
        invalid_path = Path(self.temp_directory.name) / "sample.csv"
        invalid_path.write_text("not XES", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, r"\.xes"):
            load_xes(invalid_path)


if __name__ == "__main__":
    unittest.main()
