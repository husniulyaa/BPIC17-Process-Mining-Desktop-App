"""Fluxicon Disco-inspired Case Outcomes & Cycle Time page (F03).

Wraps ``analysis.exercise_117.analyze_exercise_117`` without modifying the
underlying analysis module, presenting descriptive process-mining cohort views
instead of textbook exercise numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTableView,
)

from analysis.exercise_117 import SUBQUESTIONS, analyze_exercise_117
from ui.disco_widgets import (
    DiscoBarDelegate,
    DiscoDarkChart,
    DiscoKpiPanel,
    DiscoSidebarList,
    make_disco_search,
    style_disco_table,
)
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from utils.exporter import export_analysis_result_to_csv

COHORT_SPECS: dict[str, dict[str, str]] = {
    "11.7 A": {
        "title": "All Active Cases",
        "subtitle": "Complete case population",
        "rule": "Counts every unique case trace present in the active event log.",
    },
    "11.7 B": {
        "title": "Overall Cycle Time",
        "subtitle": "End-to-end case duration",
        "rule": "Computes cycle time per case (last event timestamp minus first event timestamp, in days) across all cases.",
    },
    "11.7 C": {
        "title": "Accepted Offers",
        "subtitle": "Contains O_Accepted",
        "rule": "Cases containing at least one 'O_Accepted' event (counted once per unique case).",
    },
    "11.7 D": {
        "title": "Refused Offers",
        "subtitle": "Contains O_Refused",
        "rule": "Cases containing at least one 'O_Refused' event (counted once per unique case; may overlap with Accepted Offers).",
    },
    "11.7 E": {
        "title": "Ended in Cancellation",
        "subtitle": "Final activity is O_Cancelled",
        "rule": "Cases whose final ordered event in the trace is 'O_Cancelled'. Mid-trace cancellations that continue afterwards are excluded.",
    },
}


class _AnalyzeOutcomesWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            self.completed.emit(analyze_exercise_117(self._event_df))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def _detail_by_code(result: dict[str, Any] | None, code: str) -> dict[str, Any]:
    for item in (result or {}).get("details", []):
        if item.get("code") == code:
            return item
    return {}


def _evidence_text(row: dict[str, Any]) -> str:
    events = row.get("evidence_events") or []
    if not events:
        first_ts = str(row.get("first_timestamp", "-"))[:19].replace("T", " ")
        last_ts = str(row.get("last_timestamp", "-"))[:19].replace("T", " ")
        return f"{row.get('n_events', '?')} events  ·  {first_ts} → {last_ts}"
    shown = ", ".join(
        f"{e['activity']} @step {int(e['index']) + 1} ({str(e['timestamp'])[:19].replace('T', ' ')})"
        for e in events[:2]
    )
    if len(events) > 2:
        shown += f" (+{len(events) - 2} more)"
    return shown


class _OutcomeCaseTableModel(QAbstractTableModel):
    HEADERS = (
        "Case ID",
        "Cycle Time (days)",
        "Matched Events",
        "Total Events",
        "Final Activity",
        "Trace Evidence",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._max_days = 1.0
        self._max_events = 1.0

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self._max_days = max(
            (float(r.get("cycle_time_days") or 0.0) for r in rows), default=1.0
        ) or 1.0
        self._max_events = max(
            (float(r.get("n_events") or 0.0) for r in rows), default=1.0
        ) or 1.0
        self.endResetModel()

    def max_for_column(self, col: int) -> float:
        if col == 1:
            return self._max_days
        if col == 3:
            return self._max_events
        return 0.0

    def case_id_at(self, row: int) -> str:
        return str(self._rows[row]["case_id"])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(row["case_id"])
            if col == 1:
                return f"{float(row['cycle_time_days']):.2f} d"
            if col == 2:
                return f"{int(row.get('matched_count', 1)):,}"
            if col == 3:
                return f"{int(row.get('n_events', 0)):,}"
            if col == 4:
                return str(row.get("last_activity", "—"))
            return _evidence_text(row)

        if role == Qt.ItemDataRole.UserRole:
            if col == 0:
                return str(row["case_id"])
            if col == 1:
                return float(row["cycle_time_days"])
            if col == 2:
                return int(row.get("matched_count", 1))
            if col == 3:
                return int(row.get("n_events", 0))
            if col == 4:
                return str(row.get("last_activity", ""))
            return _evidence_text(row)

        if role == Qt.ItemDataRole.TextAlignmentRole and col == 2:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class Exercise117Page(QWidget):
    """Fluxicon Disco-inspired Case Outcomes & Cycle Time Analysis page."""

    open_case_requested = Signal(str)
    case_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Case Outcomes & Cycle Time")
        self.event_df: pd.DataFrame | None = None
        self._result: dict[str, Any] | None = None
        self._worker: _AnalyzeOutcomesWorker | None = None
        self._dirty = False
        self._rerun_pending = False
        self._current_code = SUBQUESTIONS[0]

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left sidebar: Outcome views (replaces numbered dropdown!)
        self.sidebar = DiscoSidebarList("Outcome cohorts", self)
        self.sidebar.setFixedWidth(225)
        self._refresh_sidebar_items()
        self.sidebar.item_selected.connect(self._on_cohort_selected)
        outer.addWidget(self.sidebar)

        # Right workspace
        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(18, 14, 18, 12)
        r_layout.setSpacing(10)

        # Header & controls
        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel("All Active Cases")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E2226;")
        self.lbl_rule = QLabel(COHORT_SPECS["11.7 A"]["rule"])
        self.lbl_rule.setWordWrap(True)
        self.lbl_rule.setStyleSheet("color: #5E666E; font-size: 11px;")
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_rule)
        hdr.addLayout(title_col, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        hdr.addWidget(self.progress)

        self.btn_run = QPushButton("Recalculate")
        self.btn_run.setObjectName("toolbarBtn")
        self.btn_run.clicked.connect(self.run_analysis)
        hdr.addWidget(self.btn_run)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("toolbarBtn")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(lambda: self.export_results())
        hdr.addWidget(self.btn_export)

        r_layout.addLayout(hdr)

        # Top Disco Dark Chart + KPI panel
        top_card = QFrame()
        top_card.setObjectName("discoWhitePanel")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(12, 10, 14, 10)
        top_layout.setSpacing(14)

        self.chart = DiscoDarkChart(top_card)
        self.chart.setFixedHeight(165)
        top_layout.addWidget(self.chart, 1)

        self.kpi_panel = DiscoKpiPanel(
            [
                ("cohort_cases", "Matching cases"),
                ("share", "Share of log"),
                ("cohort_mean", "Cohort mean cycle"),
                ("all_cases", "Total log cases"),
                ("all_mean", "Global mean cycle"),
            ],
            top_card,
        )
        top_layout.addWidget(self.kpi_panel)
        r_layout.addWidget(top_card)

        # Table toolbar
        tbl_bar = QHBoxLayout()
        self.lbl_status = QLabel("Import an XES event log to analyze case outcomes and cycle times.")
        self.lbl_status.setStyleSheet("font-weight: 600; color: #495057;")
        tbl_bar.addWidget(self.lbl_status, 1)

        self.txt_search = make_disco_search("Search case ID...")
        self.txt_search.setFixedWidth(210)
        self.txt_search.textChanged.connect(self._apply_search)
        tbl_bar.addWidget(self.txt_search)

        self.btn_detail = QPushButton("Open in Cases")
        self.btn_detail.setObjectName("primaryActionBtn")
        self.btn_detail.setEnabled(False)
        self.btn_detail.clicked.connect(self._on_open_case_clicked)
        tbl_bar.addWidget(self.btn_detail)
        r_layout.addLayout(tbl_bar)

        self.model = _OutcomeCaseTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table = style_disco_table(QTableView())
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        bar_delegate = DiscoBarDelegate(self.model.max_for_column, parent=self.table)
        self.table.setItemDelegateForColumn(1, bar_delegate)
        self.table.setItemDelegateForColumn(3, bar_delegate)
        self.table.selectionModel().selectionChanged.connect(
            lambda *_: self.btn_detail.setEnabled(
                bool(self.table.selectionModel().selectedRows())
            )
        )
        self.table.doubleClicked.connect(lambda _idx: self._on_open_case_clicked())
        r_layout.addWidget(self.table, 1)

        outer.addWidget(right, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        self.event_df = event_df
        self._result = None
        self._clear_view()

        if event_df is None or event_df.empty:
            self._dirty = False
            self.lbl_status.setText("No active dataset loaded.")
            self._rerun_pending = self._worker is not None
            return

        self._dirty = True
        if self.isVisible():
            self.run_analysis()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty and self.event_df is not None and not self.event_df.empty:
            self.run_analysis()

    def run_analysis(self) -> None:
        if self.event_df is None or self.event_df.empty:
            self.lbl_status.setText("No dataset available to analyze.")
            return
        df_ref = self.event_df
        self._dirty = False
        self.btn_run.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Computing case outcomes and cycle-time metrics…")

        GLOBAL_TASK_SCHEDULER.submit(
            "outcomes_117",
            lambda: analyze_exercise_117(df_ref),
            self._on_completed,
            self._on_failed,
            high_priority=True,
        )

    def export_results(self, file_path: str | Path | None = None) -> Path | None:
        if self._result is None:
            return None
        target = file_path
        if target is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Export Case Outcomes & Cycle Time to CSV",
                "case_outcomes_cycle_time.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target = selected
        try:
            saved = export_analysis_result_to_csv(self._result, target)
            self.lbl_status.setText(f"Exported outcome metrics to {saved}")
            return saved
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", str(exc))
            return None

    # ------------------------------------------------------------ slots
    def _refresh_sidebar_items(self) -> None:
        items: list[tuple[str, str, str]] = []
        for code in SUBQUESTIONS:
            spec = COHORT_SPECS[code]
            if self._result:
                sub = _detail_by_code(self._result, code)
                cnt = int(sub.get("total_cases", 0))
                mean_d = float(sub.get("mean_cycle_time_days", 0.0))
                subtitle = f"{cnt:,} cases · mean {mean_d:.2f} d"
            else:
                subtitle = spec["subtitle"]
            items.append((code, spec["title"], subtitle))
        self.sidebar.set_items(items, select_key=self._current_code)

    def _on_completed(self, result: dict[str, Any]) -> None:
        self.progress.hide()
        self.btn_run.setEnabled(True)
        self._result = result
        self.btn_export.setEnabled(True)
        self._refresh_sidebar_items()
        self._show_cohort(self._current_code)

    def _on_failed(self, message: str) -> None:
        self.progress.hide()
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"Analysis error: {message}")

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.progress.hide()
        self.btn_run.setEnabled(True)
        if self._rerun_pending:
            self._rerun_pending = False
            if self.event_df is not None and not self.event_df.empty:
                self.run_analysis()

    def _on_cohort_selected(self, code: str) -> None:
        self._current_code = code
        self._show_cohort(code)

    def _show_cohort(self, code: str) -> None:
        spec = COHORT_SPECS.get(code, COHORT_SPECS["11.7 A"])
        self.lbl_title.setText(spec["title"])
        self.lbl_rule.setText(spec["rule"])

        if not self._result:
            self.model.set_rows([])
            return

        sub = _detail_by_code(self._result, code)
        rows = sub.get("case_evidence", [])
        self.model.set_rows(rows)

        total_log = int(self._result.get("total_cases", 0))
        all_mean = float(self._result.get("mean_cycle_time_days", 0.0))
        cnt = int(sub.get("total_cases", 0))
        mean_d = float(sub.get("mean_cycle_time_days", 0.0))
        share = (cnt / total_log * 100.0) if total_log > 0 else 0.0

        self.kpi_panel.set_value("cohort_cases", f"{cnt:,}")
        self.kpi_panel.set_value("share", f"{share:.2f}%")
        self.kpi_panel.set_value("cohort_mean", f"{mean_d:.2f} d")
        self.kpi_panel.set_value("all_cases", f"{total_log:,}")
        self.kpi_panel.set_value("all_mean", f"{all_mean:.2f} d")

        # Cycle-time distribution histogram for selected cohort
        if rows:
            days_vals = pd.Series([float(r["cycle_time_days"]) for r in rows])
            if days_vals.nunique() > 1:
                bins = pd.cut(days_vals, bins=min(36, max(2, len(days_vals))))
                hist = bins.value_counts().sort_index()
                self.chart.set_series(
                    [float(v) for v in hist.values],
                    [f"{days_vals.min():.1f} d", f"{days_vals.max():.1f} d"],
                    kind="bars",
                    x_caption=f"{spec['title']} — cycle time distribution (days)",
                    y_caption="Cases",
                )
            else:
                self.chart.set_series(
                    [float(len(days_vals))],
                    [f"{days_vals.iloc[0]:.2f} d"],
                    kind="bars",
                    x_caption="Cycle time (days)",
                    y_caption="Cases",
                )
        else:
            self.chart.clear_chart("No cases matched this outcome cohort")

        self._update_count()

    def _apply_search(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())
        self._update_count()

    def _update_count(self) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        self.lbl_status.setText(
            f"Showing {shown:,} of {total:,} matching cases"
            if total
            else "0 matching cases in this cohort"
        )

    def _clear_view(self) -> None:
        self.kpi_panel.reset()
        self.chart.clear_chart()
        self.model.set_rows([])
        self.btn_export.setEnabled(False)
        self.btn_detail.setEnabled(False)
        self._refresh_sidebar_items()

    def _on_open_case_clicked(self) -> None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            return
        source_row = self.proxy.mapToSource(selection[0]).row()
        cid = self.model.case_id_at(source_row)
        self.open_case_requested.emit(cid)
        self.case_selected.emit(cid)


__all__ = ["Exercise117Page"]
