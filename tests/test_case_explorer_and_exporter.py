"""Unit test untuk logika Case Explorer (utils.case_timeline) dan CSV exporter (utils.exporter)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from analysis.exercise_1122 import analyze_exercise_1122
from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    TIMESTAMP_ATTRIBUTE,
)
from utils.case_timeline import (
    build_case_summaries,
    filter_case_summaries,
    get_case_detail,
    get_case_events,
)
from utils.exporter import (
    export_analysis_result_to_csv,
    export_case_summaries_to_csv,
    export_case_timeline_to_csv,
    export_dataframe_to_csv,
    export_rows_to_csv,
    sanitize_filename_component,
)

try:
    from PySide6.QtWidgets import QApplication
    from ui.pages.case_explorer_page import CaseExplorerPage
    from ui.pages.exercise_1122_page import Exercise1122Page
except ImportError:
    QApplication = None
    CaseExplorerPage = None
    Exercise1122Page = None


class CaseTimelineTests(unittest.TestCase):
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                # Sengaja tidak terurut untuk menguji sorting stabil
                {
                    CASE_ID_ATTRIBUTE: "APP_02",
                    ACTIVITY_ATTRIBUTE: "O_Accepted",
                    TIMESTAMP_ATTRIBUTE: "2026-01-03T12:00:00Z",
                    "lifecycle:transition": "complete",
                    "org:resource": "User_2",
                    "OfferID": "Offer_2",
                },
                {
                    CASE_ID_ATTRIBUTE: "APP_01",
                    ACTIVITY_ATTRIBUTE: "A_Create Application",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T08:00:00Z",
                    "lifecycle:transition": "complete",
                    "org:resource": "User_1",
                    "OfferID": None,
                },
                {
                    CASE_ID_ATTRIBUTE: "APP_02",
                    ACTIVITY_ATTRIBUTE: "O_Cancelled",
                    TIMESTAMP_ATTRIBUTE: "2026-01-02T12:00:00Z",
                    "lifecycle:transition": "complete",
                    "org:resource": None,
                    "OfferID": "Offer_1",
                },
                {
                    CASE_ID_ATTRIBUTE: "APP_03_NAT",
                    ACTIVITY_ATTRIBUTE: "A_Create Application",
                    TIMESTAMP_ATTRIBUTE: "invalid-ts",
                    "lifecycle:transition": "complete",
                    "org:resource": "User_3",
                    "OfferID": None,
                },
                {
                    CASE_ID_ATTRIBUTE: "APP_03_NAT",
                    ACTIVITY_ATTRIBUTE: "O_Cancelled",
                    TIMESTAMP_ATTRIBUTE: "2026-01-02T00:00:00Z",
                    "lifecycle:transition": "complete",
                    "org:resource": "User_3",
                    "OfferID": None,
                },
            ]
        )

    def test_build_case_summaries_handles_single_multi_and_invalid_timestamps(self) -> None:
        df = self._sample_df()
        before = df.copy(deep=True)

        summaries = build_case_summaries(df)
        pd.testing.assert_frame_equal(df, before)

        by_id = {item["case_id"]: item for item in summaries}
        self.assertEqual(list(by_id.keys()), ["APP_01", "APP_02", "APP_03_NAT"])

        # Single event -> durasi 0 detik
        self.assertEqual(by_id["APP_01"]["event_count"], 1)
        self.assertEqual(by_id["APP_01"]["duration_seconds"], 0.0)
        self.assertEqual(by_id["APP_01"]["duration_display"], "00:00:00")
        self.assertFalse(by_id["APP_01"]["has_invalid_timestamps"])

        # Multi event -> 1 hari penuh
        self.assertEqual(by_id["APP_02"]["event_count"], 2)
        self.assertAlmostEqual(by_id["APP_02"]["duration_days"], 1.0)
        self.assertEqual(by_id["APP_02"]["first_activity"], "O_Cancelled")
        self.assertEqual(by_id["APP_02"]["last_activity"], "O_Accepted")

        # Invalid timestamp -> durasi None & flag True
        self.assertTrue(by_id["APP_03_NAT"]["has_invalid_timestamps"])
        self.assertIsNone(by_id["APP_03_NAT"]["duration_seconds"])
        self.assertEqual(by_id["APP_03_NAT"]["duration_display"], "—")

    def test_get_case_events_and_detail_preserve_order_deltas_and_extra_attributes(self) -> None:
        df = self._sample_df()

        events = get_case_events(df, "APP_02")
        self.assertEqual(events[ACTIVITY_ATTRIBUTE].tolist(), ["O_Cancelled", "O_Accepted"])
        self.assertIn("OfferID", events.columns)

        detail = get_case_detail(df, "APP_02")
        self.assertTrue(detail["found"])
        self.assertEqual(detail["event_count"], 2)
        self.assertTrue(detail["has_lifecycle"])
        self.assertTrue(detail["has_resource"])
        self.assertEqual(detail["extra_attributes"], ["OfferID"])

        tl = detail["timeline"]
        self.assertEqual([e["step"] for e in tl], [1, 2])
        self.assertEqual(tl[0]["delta_from_prev_seconds"], 0.0)
        self.assertEqual(tl[1]["delta_from_prev_seconds"], 86400.0)
        self.assertEqual(tl[1]["elapsed_from_start_display"], "1d 00:00:00")
        self.assertIsNone(tl[0]["resource"])
        self.assertEqual(tl[1]["resource"], "User_2")
        self.assertEqual(tl[0]["attributes"]["OfferID"], "Offer_1")

    def test_get_case_detail_for_missing_case_and_missing_optional_columns(self) -> None:
        minimal_df = pd.DataFrame(
            [
                {
                    CASE_ID_ATTRIBUTE: "C1",
                    ACTIVITY_ATTRIBUTE: "A",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T00:00:00Z",
                }
            ]
        )
        detail = get_case_detail(minimal_df, "C1")
        self.assertTrue(detail["found"])
        self.assertFalse(detail["has_lifecycle"])
        self.assertFalse(detail["has_resource"])
        self.assertIsNone(detail["timeline"][0]["lifecycle"])
        self.assertIsNone(detail["timeline"][0]["resource"])

        not_found = get_case_detail(minimal_df, "DOES_NOT_EXIST")
        self.assertFalse(not_found["found"])
        self.assertEqual(not_found["timeline"], [])

    def test_filter_case_summaries_by_query_and_allowed_subset(self) -> None:
        summaries = build_case_summaries(self._sample_df())
        by_query = filter_case_summaries(summaries, query="app_02")
        self.assertEqual([s["case_id"] for s in by_query], ["APP_02"])

        by_subset = filter_case_summaries(
            summaries,
            allowed_case_ids=["APP_01", "APP_03_NAT"],
        )
        self.assertEqual([s["case_id"] for s in by_subset], ["APP_01", "APP_03_NAT"])


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_export_exercise_1122_result_to_csv(self) -> None:
        df = pd.DataFrame(
            [
                {
                    CASE_ID_ATTRIBUTE: "CASE_1",
                    ACTIVITY_ATTRIBUTE: "O_Cancelled",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T09:00:00Z",
                },
                {
                    CASE_ID_ATTRIBUTE: "CASE_1",
                    ACTIVITY_ATTRIBUTE: "W_Followup",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T10:00:00Z",
                },
                {
                    CASE_ID_ATTRIBUTE: "CASE_1",
                    ACTIVITY_ATTRIBUTE: "O_Accepted",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T12:00:00Z",
                },
            ]
        )
        result = analyze_exercise_1122(df)
        csv_path = self.out_dir / "nested" / "ex1122.csv"

        written = export_analysis_result_to_csv(result, csv_path)
        self.assertEqual(written, csv_path)
        self.assertTrue(csv_path.is_file())

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["exercise"], "11.22")
        self.assertEqual(rows[0]["case_id"], "CASE_1")
        self.assertEqual(rows[0]["events_between_count"], "1")
        self.assertIn("O_Cancelled", rows[0]["evidence_summary"])
        self.assertIn("O_Accepted", rows[0]["evidence_summary"])

    def test_export_empty_analysis_result_writes_valid_header_only_csv(self) -> None:
        empty_result = analyze_exercise_1122(None)
        csv_path = self.out_dir / "empty_1122.csv"

        export_analysis_result_to_csv(empty_result, csv_path)
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            self.assertEqual(reader.fieldnames, ["exercise", "case_id", "evidence_summary"])
            self.assertEqual(list(reader), [])

    def test_export_exercise_117_nested_structure_to_csv(self) -> None:
        fake_117 = {
            "exercise": "11.7",
            "rule": "summary",
            "total_cases": 1,
            "case_ids": ["C1"],
            "details": [
                {
                    "code": "11.7 C",
                    "title": "Successful Cases",
                    "total_cases": 1,
                    "case_ids": ["C1"],
                    "case_evidence": [
                        {
                            "case_id": "C1",
                            "cycle_time_days": 1.5,
                            "matched_count": 1,
                            "n_events": 3,
                            "last_activity": "O_Accepted",
                            "first_timestamp": "2026-01-01T00:00:00+00:00",
                            "last_timestamp": "2026-01-02T12:00:00+00:00",
                            "evidence_events": [
                                {
                                    "activity": "O_Accepted",
                                    "timestamp": "2026-01-02T12:00:00+00:00",
                                    "index": 2,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        csv_path = self.out_dir / "ex117.csv"
        export_analysis_result_to_csv(fake_117, csv_path)

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subquestion"], "11.7 C")
        self.assertEqual(rows[0]["case_id"], "C1")

    def test_export_case_timeline_and_summaries_to_csv(self) -> None:
        df = pd.DataFrame(
            [
                {
                    CASE_ID_ATTRIBUTE: "C_01",
                    ACTIVITY_ATTRIBUTE: "B",
                    TIMESTAMP_ATTRIBUTE: "2026-01-02T00:00:00Z",
                },
                {
                    CASE_ID_ATTRIBUTE: "C_01",
                    ACTIVITY_ATTRIBUTE: "A",
                    TIMESTAMP_ATTRIBUTE: "2026-01-01T00:00:00Z",
                },
            ]
        )
        before = df.copy(deep=True)

        timeline_path = self.out_dir / "timeline_c01.csv"
        export_case_timeline_to_csv(df, "C_01", timeline_path)
        pd.testing.assert_frame_equal(df, before)

        exported_df = pd.read_csv(timeline_path)
        self.assertEqual(exported_df["event_step"].tolist(), [1, 2])
        self.assertEqual(exported_df[ACTIVITY_ATTRIBUTE].tolist(), ["A", "B"])

        summaries_path = self.out_dir / "summaries.csv"
        summaries = build_case_summaries(df)
        export_case_summaries_to_csv(summaries, summaries_path)
        sum_df = pd.read_csv(summaries_path)
        self.assertEqual(sum_df["case_id"].tolist(), ["C_01"])
        self.assertEqual(int(sum_df["event_count"].iloc[0]), 2)

        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            export_case_timeline_to_csv(df, "UNKNOWN", self.out_dir / "missing.csv")

    def test_export_validation_and_helpers(self) -> None:
        with self.assertRaises(ValueError):
            export_rows_to_csv([], "")
        with self.assertRaises(ValueError):
            export_rows_to_csv([], self.out_dir)
        with self.assertRaises(TypeError):
            export_dataframe_to_csv("not-a-df", self.out_dir / "bad.csv")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            export_analysis_result_to_csv(["not-a-dict"], self.out_dir / "bad.csv")  # type: ignore[arg-type]

        self.assertEqual(sanitize_filename_component("Application/123:45"), "Application_123_45")
        self.assertEqual(sanitize_filename_component("   "), "export")


class TabularImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_csv_xlsx_xmx_and_json_import_and_column_mapping(self) -> None:
        from utils.tabular_importer import (
            ROLE_ACTIVITY,
            ROLE_CASE,
            ROLE_IGNORE,
            ROLE_OTHER,
            ROLE_RESOURCE,
            ROLE_TIMESTAMP,
            apply_column_mapping,
            detect_column_roles,
            read_raw_data_file,
        )

        # 1. Purchasing CSV similar to Disco screenshot (DD/MM/YYYY HH:MM + Start & Complete TS)
        csv_file = self.dir_path / "purchasing.csv"
        csv_file.write_text(
            "Case ID;Start Timestamp;Complete Timestamp;Activity;Resource;Role\n"
            "339;16/02/2011 14:31;16/02/2011 15:23;Create Purchase Requisition;Nico Ojenbeer;Requester\n"
            "339;17/02/2011 09:34;17/02/2011 09:40;Analyze Purchase Requisition;Maris Freeman;Manager\n"
            "940;17/05/2011 06:31;17/05/2011 07:08;Create Purchase Requisition;Immanuel;Requester\n",
            encoding="utf-8",
        )
        raw_csv, info_csv = read_raw_data_file(csv_file)
        self.assertFalse(info_csv["is_xes"])
        self.assertEqual(len(raw_csv), 3)

        roles = detect_column_roles(raw_csv)
        self.assertEqual(roles["Case ID"], ROLE_CASE)
        self.assertEqual(roles["Activity"], ROLE_ACTIVITY)
        self.assertEqual(roles["Complete Timestamp"], ROLE_TIMESTAMP)
        self.assertEqual(roles["Resource"], ROLE_RESOURCE)

        # Also support marking BOTH Start & Complete Timestamp as ROLE_TIMESTAMP + excluding Role
        roles["Start Timestamp"] = ROLE_TIMESTAMP
        roles["Role"] = ROLE_IGNORE
        mapped_df, meta = apply_column_mapping(raw_csv, roles)
        self.assertEqual(meta["case_count"], 2)
        self.assertEqual(meta["event_count"], 3)
        self.assertNotIn("Role", mapped_df.columns)
        self.assertEqual(mapped_df["org:resource"].iloc[0], "Nico Ojenbeer")

        # 2. Excel .xlsx round-trip
        xlsx_file = self.dir_path / "events.xlsx"
        raw_csv.to_excel(xlsx_file, index=False)
        raw_xlsx, _ = read_raw_data_file(xlsx_file)
        self.assertEqual(len(raw_xlsx), 3)

        # 3. MXML / .xmx file
        xmx_file = self.dir_path / "sample.xmx"
        xmx_file.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<WorkflowLog>
  <Process id="P1">
    <ProcessInstance id="CASE_XMX_1">
      <AuditTrailEntry>
        <WorkflowModelElement>O_Cancelled</WorkflowModelElement>
        <EventType>complete</EventType>
        <Timestamp>2026-01-01T09:00:00Z</Timestamp>
        <Originator>Officer_1</Originator>
      </AuditTrailEntry>
      <AuditTrailEntry>
        <WorkflowModelElement>O_Accepted</WorkflowModelElement>
        <EventType>complete</EventType>
        <Timestamp>2026-01-02T10:00:00Z</Timestamp>
        <Originator>Officer_2</Originator>
      </AuditTrailEntry>
    </ProcessInstance>
  </Process>
</WorkflowLog>""",
            encoding="utf-8",
        )
        raw_xmx, _ = read_raw_data_file(xmx_file)
        xmx_roles = detect_column_roles(raw_xmx)
        mapped_xmx, xmx_meta = apply_column_mapping(raw_xmx, xmx_roles)
        self.assertEqual(xmx_meta["case_count"], 1)
        self.assertEqual(analyze_exercise_1122(mapped_xmx)["case_ids"], ["CASE_XMX_1"])

        # 4. JSON file
        json_file = self.dir_path / "events.json"
        raw_csv.to_json(json_file, orient="records")
        raw_json, _ = read_raw_data_file(json_file)
        self.assertEqual(len(raw_json), 3)
        self.assertEqual(detect_column_roles(raw_json)["Role"], ROLE_OTHER)


@unittest.skipIf(QApplication is None, "PySide6 is required for GUI page smoke tests.")
class GuiPageSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_pages_instantiate_and_accept_empty_data(self) -> None:
        p1122 = Exercise1122Page()
        p1122.set_event_data(None)
        self.assertIsNone(p1122.get_result())

        explorer = CaseExplorerPage()
        explorer.set_event_data(None)
        self.assertFalse(explorer.select_case("MISSING"))

    def test_disco_main_window_columns_dialog_and_process_map(self) -> None:
        from ui.loading_dialog import DiscoLoadingDialog
        from ui.main_window import MainWindow, _demo_df
        from ui.pages.column_mapping_page import ColumnMappingPage
        from ui.pages.process_map_page import compute_process_map_data
        from utils.case_timeline import build_case_summaries_and_variants

        df = _demo_df(25)
        summaries, variants = build_case_summaries_and_variants(df)
        self.assertEqual(len(summaries), 25)
        self.assertGreaterEqual(len(variants), 1)
        self.assertEqual(sum(v["case_count"] for v in variants), 25)

        map_data = compute_process_map_data(df)
        self.assertEqual(map_data["total_cases"], 25)
        self.assertIn("A_Create Application", map_data["activities"])
        self.assertGreater(len(map_data["edges"]), 0)

        col_page = ColumnMappingPage()
        col_page.set_raw_dataframe(df, source_path="demo.csv")
        self.assertEqual(col_page.model.columnCount(), df.shape[1])

        win = MainWindow()
        self.assertIn("Disco - Lite", win.windowTitle())
        self.assertIn("Kelompok 7", win.windowTitle())
        for btn in win.nav_buttons:
            label_txt = btn.text()
            for num in ("11.7", "11.15", "11.18", "11.22"):
                self.assertNotIn(num, label_txt)

        dlg = DiscoLoadingDialog(win)
        dlg.start("Testing…", "Stage 1")
        dlg.update_stage("Stage 2")
        dlg.finish()

        win.set_event_data(df, path="(Unit Test Sample)")
        self.assertEqual(len(win.pages), 8)
        win.close()


if __name__ == "__main__":
    unittest.main()
