"""Fluxicon Disco-inspired BPIC17 Process Mining Workspace (PySide6).

Branding: Disco - Lite (by Kelompok 7)

Integration contract preserved:
    MainWindow.event_df
    MainWindow.set_event_data(df, path=None)
    MainWindow.dataset_requested
    MainWindow.dataset_path
    QSS
"""

from __future__ import annotations

from pathlib import Path
import random
import sys
from typing import Any, Sequence

import pandas as pd
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.disco_widgets import DISCO_QSS
from ui.loading_dialog import DiscoLoadingDialog
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from ui.pages.case_explorer_page import CaseExplorerPage
from ui.pages.column_mapping_page import ColumnMappingPage
from ui.pages.exercise_1115_page import Exercise1115Page
from ui.pages.exercise_1118_page import Exercise1118Page
from ui.pages.exercise_1122_page import Exercise1122Page
from ui.pages.exercise_117_page import Exercise117Page
from ui.pages.overview_page import OverviewPage
from ui.pages.process_map_page import ProcessMapPage
from utils.tabular_importer import (
    SUPPORTED_FILE_FILTER,
    apply_column_mapping,
    read_raw_data_file,
)

QSS = DISCO_QSS

TAB_COLUMNS = 0
TAB_MAP = 1
TAB_STATISTICS = 2
TAB_OUTCOMES = 3
TAB_FRAUD_REWORK = 4
TAB_SAME_OFFICER = 5
TAB_REACCEPTED = 6
TAB_CASES = 7

TAB_SPECS: list[tuple[str, str]] = [
    ("Columns", "Configure Case ID, Timestamp, Activity, Resource / Person & Attributes"),
    ("Map", "Directly-Follows Process Map — Frequency & Performance"),
    ("Statistics", "Global Event Log Statistics & Attribute Distributions"),
    ("Outcomes && Cycle Time", "Case Outcomes, Offer Decisions & Cycle Time Cohorts"),
    ("Fraud Rework", "Repeated Potential Fraud Assessments"),
    ("Same-Officer Fraud", "Same-Officer Repeated Fraud Assessments"),
    ("Cancelled → Accepted", "Re-Accepted Offers Following Cancellation"),
    ("Cases", "Individual Case Traces, Process Variants & Attribute Inspector"),
]


class _FileReadWorker(QThread):
    """Background worker reading any supported file (.xes, .csv, .xlsx, .xmx, etc.)."""

    stage_changed = Signal(str)
    completed = Signal(object, dict)
    failed = Signal(str)

    def __init__(
        self,
        file_path: str,
        *,
        encoding: str = "utf-8",
        delimiter: str = "auto",
        use_quotes: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_path = file_path
        self._encoding = encoding
        self._delimiter = delimiter
        self._use_quotes = use_quotes

    def run(self) -> None:
        try:
            fname = Path(self._file_path).name
            self.stage_changed.emit(f"Reading '{fname}'…")
            extract_dir = Path(__file__).resolve().parent.parent / "data"
            df, info = read_raw_data_file(
                self._file_path,
                encoding=self._encoding,
                delimiter=self._delimiter,
                use_quotes=self._use_quotes,
                extract_dir=extract_dir,
            )
            self.stage_changed.emit(
                f"Loaded {len(df):,} rows · preparing column configuration…"
            )
            self.completed.emit(df, info)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _ColumnMapWorker(QThread):
    """Background worker applying user-selected column mappings to build event_df."""

    stage_changed = Signal(str)
    completed = Signal(object, dict, str)
    failed = Signal(str)

    def __init__(
        self,
        raw_df: pd.DataFrame,
        role_map: dict[str, str],
        ts_format: str,
        source_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._raw_df = raw_df
        self._role_map = dict(role_map)
        self._ts_format = ts_format
        self._source_path = source_path

    def run(self) -> None:
        try:
            self.stage_changed.emit(
                f"Parsing timestamps and mapping {len(self._raw_df):,} events…"
            )
            event_df, meta = apply_column_mapping(
                self._raw_df,
                self._role_map,
                timestamp_format=self._ts_format,
            )
            self.stage_changed.emit(
                f"Validated {meta['case_count']:,} cases ({meta['event_count']:,} events)…"
            )
            self.completed.emit(event_df, meta, self._source_path)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Main Disco - Lite (by Kelompok 7) desktop workspace."""

    dataset_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Disco - Lite (by Kelompok 7) — Process Mining Workspace")
        self.resize(1440, 870)
        self.setMinimumSize(1160, 680)

        self.event_df: pd.DataFrame | None = None
        self.dataset_path: str | None = None
        self._file_worker: _FileReadWorker | None = None
        self._map_worker: _ColumnMapWorker | None = None
        self._loading_dialog = DiscoLoadingDialog(self)

        root = QWidget()
        root.setObjectName("discoRoot")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --------------------------------------------------- TOP DISCO CHROME
        header = QFrame()
        header.setObjectName("discoHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 16, 0)
        header_layout.setSpacing(8)

        # Left toolbar controls (Open Data + Sample Log + Active Log Pill)
        left_tools = QHBoxLayout()
        left_tools.setContentsMargins(0, 0, 0, 6)
        left_tools.setSpacing(6)

        self.import_btn = QPushButton("Open Data…")
        self.import_btn.setObjectName("primaryActionBtn")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.setToolTip(
            "Open XES, XES.GZ, CSV, TSV, XLSX, XLS, XML, XMX, MXML, JSON, or Parquet"
        )
        self.import_btn.clicked.connect(self._on_import)
        left_tools.addWidget(self.import_btn)

        self.demo_btn = QPushButton("Sample Log")
        self.demo_btn.setObjectName("toolbarBtn")
        self.demo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.demo_btn.setToolTip("Load a synthetic BPIC17 sample log to preview all features")
        self.demo_btn.clicked.connect(self._load_sample_log)
        left_tools.addWidget(self.demo_btn)

        ds_box = QFrame()
        ds_box.setObjectName("datasetSelectorBox")
        ds_box_layout = QHBoxLayout(ds_box)
        ds_box_layout.setContentsMargins(8, 3, 8, 3)
        ds_box_layout.setSpacing(6)
        self.lbl_dataset_name = QLabel("No data loaded")
        self.lbl_dataset_name.setMaximumWidth(175)
        self.lbl_dataset_name.setStyleSheet("font-weight: 600; color: #22262A;")
        self.lbl_dataset_badge = QLabel("0 cases")
        self.lbl_dataset_badge.setStyleSheet(
            "background: #6B727A; color: #FFFFFF; border-radius: 3px; "
            "padding: 1px 6px; font-size: 10px; font-weight: 700;"
        )
        ds_box_layout.addWidget(self.lbl_dataset_name)
        ds_box_layout.addWidget(self.lbl_dataset_badge)
        left_tools.addWidget(ds_box)

        header_layout.addLayout(left_tools)
        header_layout.addStretch(1)

        # Center Disco Folder Tabs (aligned flush to bottom of header)
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(0, 4, 0, 0)
        tabs_row.setSpacing(2)

        self.stack = QStackedWidget()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.nav_buttons: list[QPushButton] = []

        self.columns_page = ColumnMappingPage()
        self.map_page = ProcessMapPage()
        self.overview_page = OverviewPage()
        self.outcomes_page = Exercise117Page()
        self.fraud_rework_page = Exercise1115Page()
        self.same_officer_page = Exercise1118Page()
        self.reaccepted_page = Exercise1122Page()
        self.case_explorer_page = CaseExplorerPage()

        # Analysis/visualization pages that consume standard event_df
        self.analysis_pages: list[QWidget] = [
            self.map_page,
            self.overview_page,
            self.outcomes_page,
            self.fraud_rework_page,
            self.same_officer_page,
            self.reaccepted_page,
            self.case_explorer_page,
        ]
        self.pages: list[QWidget] = [self.columns_page, *self.analysis_pages]

        for idx, ((tab_label, tab_tip), page) in enumerate(
            zip(TAB_SPECS, self.pages)
        ):
            btn = QPushButton(tab_label)
            btn.setObjectName("discoTab")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tab_tip)
            self.group.addButton(btn, idx)
            tabs_row.addWidget(btn, 0, Qt.AlignmentFlag.AlignBottom)
            self.stack.addWidget(page)
            self.nav_buttons.append(btn)

        self.group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_buttons[TAB_STATISTICS].setChecked(True)
        self.stack.setCurrentIndex(TAB_STATISTICS)

        header_layout.addLayout(tabs_row)
        header_layout.addStretch(1)

        # Right Status + Brand ("Disco - Lite" / "by Kelompok 7")
        right_brand = QHBoxLayout()
        right_brand.setContentsMargins(0, 0, 0, 5)
        right_brand.setSpacing(12)

        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.RichText)
        right_brand.addWidget(self.status)

        brand_stack = QVBoxLayout()
        brand_stack.setContentsMargins(0, 0, 0, 0)
        brand_stack.setSpacing(0)
        lbl_brand = QLabel("Disco - Lite")
        lbl_brand.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        lbl_brand.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #52575D; letter-spacing: 0.3px;"
        )
        lbl_team = QLabel("by Kelompok 7")
        lbl_team.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        lbl_team.setStyleSheet(
            "font-size: 10px; font-weight: 600; color: #727981;"
        )
        brand_stack.addWidget(lbl_brand)
        brand_stack.addWidget(lbl_team)
        right_brand.addLayout(brand_stack)

        header_layout.addLayout(right_brand)
        outer.addWidget(header)

        # --------------------------------------------------- WORKSPACE STACK
        outer.addWidget(self.stack, 1)

        # --------------------------------------------------- BOTTOM FOOTER
        footer = QFrame()
        footer.setObjectName("discoFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 5, 16, 5)
        footer_layout.setSpacing(12)

        self.foot_path = QLabel("No file selected")
        footer_layout.addWidget(self.foot_path, 1)

        self.foot_shape = QLabel("")
        footer_layout.addWidget(self.foot_shape)

        btn_jump_cols = QPushButton("Configure Columns")
        btn_jump_cols.setObjectName("footerBtn")
        btn_jump_cols.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_jump_cols.clicked.connect(lambda: self._switch_to_tab(TAB_COLUMNS))
        footer_layout.addWidget(btn_jump_cols)

        btn_jump_cases = QPushButton("Cases")
        btn_jump_cases.setObjectName("footerBtn")
        btn_jump_cases.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_jump_cases.clicked.connect(lambda: self._switch_to_tab(TAB_CASES))
        footer_layout.addWidget(btn_jump_cases)

        btn_footer_export = QPushButton("Export CSV")
        btn_footer_export.setObjectName("footerBtn")
        btn_footer_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_footer_export.clicked.connect(self._export_active_page)
        footer_layout.addWidget(btn_footer_export)

        outer.addWidget(footer)

        # Wire ColumnMappingPage signals
        self.columns_page.open_file_requested.connect(self._on_import)
        self.columns_page.reload_csv_requested.connect(self._reload_csv_with_options)
        self.columns_page.mapping_applied.connect(self._apply_column_mapping)

        # Wire cross-page Case Explorer navigation
        self.overview_page.open_case_requested.connect(
            lambda cid: self.open_case_in_explorer(cid)
        )
        self.outcomes_page.open_case_requested.connect(
            lambda cid: self.open_case_in_explorer(
                cid, ["O_Accepted", "O_Refused", "O_Cancelled"]
            )
        )
        self.fraud_rework_page.open_case_requested.connect(
            lambda cid: self.open_case_in_explorer(cid, ["W_Assess Potential Fraud"])
        )
        self.same_officer_page.open_case_requested.connect(
            lambda cid: self.open_case_in_explorer(cid, ["W_Assess Potential Fraud"])
        )
        self.reaccepted_page.open_case_requested.connect(
            lambda cid: self.open_case_in_explorer(cid, ["O_Cancelled", "O_Accepted"])
        )

        self._set_status("Ready", None)

    # --------------------------------------------------- PUBLIC CONTRACT
    def set_event_data(
        self,
        df: pd.DataFrame | None,
        path: str | None = None,
        *,
        sync_columns_page: bool = True,
        case_count: int | None = None,
    ) -> None:
        GLOBAL_TASK_SCHEDULER.reset_generation()
        self.event_df = df
        if path is not None:
            self.dataset_path = path

        if sync_columns_page:
            self.columns_page.set_raw_dataframe(
                df,
                source_path=self.dataset_path or "",
            )

        for page in self.analysis_pages:
            page.set_event_data(df)

        if df is None or df.empty:
            self.lbl_dataset_name.setText("No data loaded")
            self.lbl_dataset_badge.setText("0 cases")
            self._set_status("No dataset loaded", None)
            self.foot_shape.setText("")
        else:
            case_cnt = (
                int(case_count)
                if case_count is not None
                else (
                    int(df["case:concept:name"].nunique())
                    if "case:concept:name" in df.columns
                    else 0
                )
            )
            display_name = (
                Path(self.dataset_path).stem
                if self.dataset_path and not self.dataset_path.startswith("(")
                else (self.dataset_path or "Active Event Log")
            )
            if display_name.lower().endswith(".xes"):
                display_name = display_name[:-4]
            self.lbl_dataset_name.setText(display_name)
            self.lbl_dataset_badge.setText(f"{case_cnt:,} cases")
            self._set_status(f"{len(df):,} events", "ok")
            self.foot_shape.setText(
                f"{case_cnt:,} cases  ·  {len(df):,} events  ·  {df.shape[1]} attributes"
            )

        self.foot_path.setText(self.dataset_path or "No file selected")

    def load_data_file(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        delimiter: str = "auto",
        use_quotes: bool = True,
    ) -> None:
        """Load any supported data file asynchronously with a modal loading pop-up."""
        if self._file_worker is not None and self._file_worker.isRunning():
            return

        self.dataset_path = path
        self.foot_path.setText(path)
        self._set_status("Loading data…", "busy")

        fname = Path(path).name
        if self.isVisible():
            self._loading_dialog.start(
                f"Opening '{fname}'…",
                "Reading file and inspecting data columns…",
            )

        worker = _FileReadWorker(
            path,
            encoding=encoding,
            delimiter=delimiter,
            use_quotes=use_quotes,
            parent=self,
        )
        worker.stage_changed.connect(self._loading_dialog.update_stage)
        worker.completed.connect(self._on_raw_file_loaded)
        worker.failed.connect(self._on_file_load_failed)
        worker.finished.connect(self._on_file_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._file_worker = worker
        worker.start()

    def show_error(self, message: str) -> None:
        self._loading_dialog.finish()
        self._set_status(message, "err")
        if self.isVisible():
            QMessageBox.critical(self, "Disco - Lite · Load Error", message)

    def open_case_in_explorer(
        self,
        case_id: str,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        """Switch to the Cases tab and display the requested case trace."""
        self._switch_to_tab(TAB_CASES)
        self.case_explorer_page.select_case(
            case_id,
            highlight_activities=highlight_activities,
        )

    # --------------------------------------------------- INTERNALS
    def _on_raw_file_loaded(self, df: pd.DataFrame, info: dict[str, Any]) -> None:
        self._loading_dialog.finish()
        src_path = str(info.get("source_path") or self.dataset_path or "")

        if info.get("is_xes"):
            # XES already matches standard contract -> load workspace AND populate Columns tab
            self.set_event_data(
                df,
                path=src_path,
                sync_columns_page=True,
                case_count=info.get("case_count"),
            )
            if self.stack.currentIndex() == TAB_COLUMNS:
                self._switch_to_tab(TAB_MAP)
        else:
            # CSV / Excel / XML / XMX / JSON -> open Disco Column Configuration screen!
            self.columns_page.set_raw_dataframe(df, source_path=src_path)
            fname = Path(src_path).name if src_path else "Data table"
            self.lbl_dataset_name.setText(Path(fname).stem)
            self.lbl_dataset_badge.setText(f"{len(df):,} rows")
            self._set_status("Configure columns to start", "busy")
            self._switch_to_tab(TAB_COLUMNS)

    def _on_file_load_failed(self, msg: str) -> None:
        self.show_error(f"Could not read file: {msg}")

    def _on_file_worker_finished(self) -> None:
        self._file_worker = None

    def _reload_csv_with_options(
        self,
        path: str,
        encoding: str,
        delimiter: str,
        use_quotes: bool,
    ) -> None:
        self.load_data_file(
            path,
            encoding=encoding,
            delimiter=delimiter,
            use_quotes=use_quotes,
        )

    def _apply_column_mapping(
        self,
        raw_df: pd.DataFrame,
        role_map: dict[str, str],
        ts_format: str,
        source_path: str,
    ) -> None:
        if self._map_worker is not None and self._map_worker.isRunning():
            return

        self._set_status("Building event log…", "busy")
        if self.isVisible():
            self._loading_dialog.start(
                "Building Process Event Log…",
                "Mapping Case ID, Timestamp, Activity, and Resource columns…",
            )

        worker = _ColumnMapWorker(
            raw_df,
            role_map,
            ts_format,
            source_path or (self.dataset_path or ""),
            parent=self,
        )
        worker.stage_changed.connect(self._loading_dialog.update_stage)
        worker.completed.connect(self._on_mapping_completed)
        worker.failed.connect(self._on_mapping_failed)
        worker.finished.connect(self._on_map_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._map_worker = worker
        worker.start()

    def _on_mapping_completed(
        self,
        event_df: pd.DataFrame,
        meta: dict[str, Any],
        source_path: str,
    ) -> None:
        self._loading_dialog.finish()
        self.set_event_data(
            event_df,
            path=source_path or self.dataset_path,
            sync_columns_page=False,
            case_count=meta.get("case_count"),
        )
        self._switch_to_tab(TAB_MAP)

    def _on_mapping_failed(self, msg: str) -> None:
        self.show_error(f"Column mapping error: {msg}")

    def _on_map_worker_finished(self) -> None:
        self._map_worker = None

    def _switch_to_tab(self, index: int) -> None:
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)
            self.stack.setCurrentIndex(index)

    def _export_active_page(self) -> None:
        current = self.stack.currentWidget()
        if hasattr(current, "export_results"):
            current.export_results()
        elif hasattr(current, "export_current_case_csv"):
            current.export_current_case_csv()
        elif hasattr(current, "export_current_table"):
            current.export_current_table()
        else:
            self._switch_to_tab(TAB_CASES)

    def _set_status(self, text: str, state: str | None) -> None:
        dot_color = {
            "ok": "#2A8F47",
            "err": "#C93B3B",
            "busy": "#D9822B",
            None: "#7D858D",
        }.get(state, "#7D858D")

        self.status.setText(
            f'<span style="color:{dot_color}; font-size:13px;">●</span>&nbsp;'
            f'<span style="color:#3A4046; font-weight:600;">{text}</span>'
        )

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Event Log or Tabular Data File",
            self.dataset_path or "",
            SUPPORTED_FILE_FILTER,
        )
        if path:
            self.dataset_requested.emit(path)
            # If no external handler connected to dataset_requested, load directly
            if self.receivers(self.dataset_requested) == 0:
                self.load_data_file(path)

    def _load_sample_log(self) -> None:
        df = _demo_df(160)
        self.set_event_data(df, path="(BPIC17 Sample Log)", sync_columns_page=True)
        if self.stack.currentIndex() == TAB_COLUMNS:
            self._switch_to_tab(TAB_MAP)


def _demo_df(n: int = 160) -> pd.DataFrame:
    """Realistic BPIC17-style sample log exercising all cohorts, fraud rework, & re-acceptance."""
    rng = random.Random(42)
    rows: list[dict[str, Any]] = []

    for i in range(n):
        cid = f"Application_{652800 + i}"
        t = pd.Timestamp("2016-01-01T08:00:00Z") + pd.Timedelta(hours=rng.randint(0, 4000))
        loan_goal = rng.choice(
            ["Home improvement", "Car", "Existing loan takeover", "Debt consolidation"]
        )
        req_amt = float(rng.choice([5000, 10000, 15000, 25000, 35000]))

        def add_ev(act: str, res: str | None, lc: str = "complete", mins: int = 15) -> None:
            nonlocal t
            t = t + pd.Timedelta(minutes=mins)
            rows.append(
                {
                    "case:concept:name": cid,
                    "concept:name": act,
                    "time:timestamp": t,
                    "org:resource": res,
                    "lifecycle:transition": lc,
                    "LoanGoal": loan_goal,
                    "RequestedAmount": req_amt,
                }
            )

        u1 = f"User_{rng.randint(1, 25)}"
        u2 = f"User_{rng.randint(1, 25)}"
        add_ev("A_Create Application", u1, mins=0)
        add_ev("A_Submitted", u1, mins=rng.randint(1, 30))
        add_ev("W_Handle leads", u1, mins=rng.randint(10, 240))
        add_ev("W_Complete application", u2, mins=rng.randint(30, 720))
        add_ev("A_Accepted", u2, mins=rng.randint(15, 180))
        add_ev("O_Create Offer", u2, mins=rng.randint(5, 90))
        add_ev("O_Sent (mail and online)", u2, mins=rng.randint(2, 30))
        add_ev("W_Call after offers", u2, mins=rng.randint(120, 2880))

        bucket = i % 10
        if bucket in (0, 1):
            add_ev("O_Cancelled", u2, mins=rng.randint(60, 1440))
            add_ev("O_Create Offer", u1, mins=rng.randint(30, 360))
            add_ev("O_Sent (mail and online)", u1, mins=rng.randint(5, 45))
            add_ev("O_Accepted", u1, mins=rng.randint(120, 2880))
            add_ev("A_Pending", u1, mins=rng.randint(10, 120))
        elif bucket == 2:
            officer = f"User_Fraud_{rng.randint(1, 4)}"
            add_ev("W_Assess Potential Fraud", officer, lc="start", mins=60)
            add_ev("W_Assess Potential Fraud", officer, lc="complete", mins=45)
            add_ev("W_Assess Potential Fraud", officer, lc="complete", mins=180)
            add_ev("O_Refused", officer, mins=90)
        elif bucket == 3:
            add_ev("W_Assess Potential Fraud", "User_Fraud_1", lc="complete", mins=60)
            add_ev("W_Assess Potential Fraud", "User_Fraud_2", lc="complete", mins=150)
            add_ev("O_Accepted", u2, mins=240)
        elif bucket in (4, 5):
            add_ev("O_Cancelled", u2, mins=rng.randint(240, 4320))
        elif bucket == 6:
            add_ev("W_Validate application", u1, mins=360)
            add_ev("O_Refused", u1, mins=120)
        else:
            add_ev("W_Validate application", u1, mins=rng.randint(60, 1440))
            add_ev("O_Accepted", u1, mins=rng.randint(60, 1440))
            add_ev("A_Pending", u1, mins=rng.randint(15, 90))

    return pd.DataFrame(rows)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    window = MainWindow()
    if "--demo" in sys.argv:
        window._load_sample_log()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
