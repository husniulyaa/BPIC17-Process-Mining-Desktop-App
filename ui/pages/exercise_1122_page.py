"""Fluxicon Disco-inspired Re-Accepted Cancelled Offers page (F06).

Displays results from ``analysis.exercise_1122.analyze_exercise_1122`` using
descriptive process-mining terminology, a dark turnaround-time distribution
chart, inline proportional bar tables, a Disco step-flow evidence viewer,
Case Explorer navigation, and CSV export.
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
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from analysis.exercise_1122 import (
    ACCEPTED_ACTIVITY,
    CANCELLED_ACTIVITY,
    LIFECYCLE_ATTRIBUTE,
    RESOURCE_ATTRIBUTE,
    analyze_exercise_1122,
)
from ui.disco_widgets import (
    DiscoBarDelegate,
    DiscoDarkChart,
    DiscoKpiPanel,
    DiscoSegmentedToggle,
    DiscoTraceGraphWidget,
    make_disco_search,
    style_disco_table,
)
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from utils.case_timeline import format_human_duration
from utils.exporter import export_analysis_result_to_csv


class _AnalyzeReAcceptedWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            self.completed.emit(analyze_exercise_1122(self._event_df))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _ReAcceptedCaseModel(QAbstractTableModel):
    HEADERS = (
        "Case ID",
        "First O_Cancelled",
        "Subsequent O_Accepted",
        "Turnaround",
        "Steps Between",
        "Total Events",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []
        self._max_turnaround = 1.0
        self._max_events = 1.0

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self._max_turnaround = max(
            (float(r.get("time_between_seconds") or 0.0) for r in rows),
            default=1.0,
        ) or 1.0
        self._max_events = max(
            (float(r.get("total_events") or 0.0) for r in rows),
            default=1.0,
        ) or 1.0
        self.endResetModel()

    def max_for_column(self, col: int) -> float:
        if col == 3:
            return self._max_turnaround
        if col == 5:
            return self._max_events
        return 0.0

    def row_at(self, row_index: int) -> dict[str, Any] | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

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

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(row.get("case_id", ""))
            if col == 1:
                return str(row.get("first_cancelled_timestamp") or "—")[:19].replace("T", " ")
            if col == 2:
                return str(
                    row.get("first_accepted_after_cancelled_timestamp") or "—"
                )[:19].replace("T", " ")
            if col == 3:
                return format_human_duration(row.get("time_between_seconds"))
            if col == 4:
                return f"{int(row.get('events_between_count', 0)):,}"
            if col == 5:
                return f"{int(row.get('total_events', 0)):,}"

        if role == Qt.ItemDataRole.UserRole:
            if col == 0:
                return str(row.get("case_id", ""))
            if col == 1:
                return str(row.get("first_cancelled_timestamp") or "")
            if col == 2:
                return str(row.get("first_accepted_after_cancelled_timestamp") or "")
            if col == 3:
                return float(row.get("time_between_seconds") or 0.0)
            if col == 4:
                return int(row.get("events_between_count") or 0)
            if col == 5:
                return int(row.get("total_events") or 0)

        if role == Qt.ItemDataRole.TextAlignmentRole and col == 4:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class _EvidenceTableModel(QAbstractTableModel):
    HEADERS = (
        "Step",
        "Activity",
        "Timestamp (UTC)",
        "Lifecycle",
        "Resource",
        "Evidence Role",
    )

    _ROLE_LABELS = {
        "first_o_cancelled": "Initial O_Cancelled",
        "first_o_accepted_after_cancelled": "Subsequent O_Accepted",
        "o_accepted_after_cancelled": "Additional O_Accepted",
        "o_accepted_not_after_cancelled": "Earlier/equal O_Accepted",
        "o_cancelled": "Additional O_Cancelled",
        "intermediate": "Intermediate step",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: list[dict[str, Any]] = []

    def set_events(self, events: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._events = list(events)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._events)

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
        ev = self._events[index.row()]
        col = index.column()
        act = str(ev.get("activity", ""))

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(ev.get("step", ""))
            if col == 1:
                return act
            if col == 2:
                return str(ev.get("timestamp") or "NaT")
            if col == 3:
                return (
                    "(unavailable)"
                    if LIFECYCLE_ATTRIBUTE not in ev
                    else str(ev.get(LIFECYCLE_ATTRIBUTE) or "—")
                )
            if col == 4:
                return (
                    "(unavailable)"
                    if RESOURCE_ATTRIBUTE not in ev
                    else str(ev.get(RESOURCE_ATTRIBUTE) or "—")
                )
            raw_role = str(ev.get("role", ""))
            return self._ROLE_LABELS.get(raw_role, raw_role or "—")

        if role == Qt.ItemDataRole.BackgroundRole:
            if act == CANCELLED_ACTIVITY:
                return QBrush(QColor("#FDECEC"))
            if act == ACCEPTED_ACTIVITY:
                return QBrush(QColor("#E8F7EE"))
        return None


class Exercise1122Page(QWidget):
    """Fluxicon Disco-inspired Re-Accepted Cancelled Offers page (F06)."""

    open_case_requested = Signal(str)
    case_selected = Signal(str)
    result_ready = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Re-Accepted Cancelled Offers")

        self.event_df: pd.DataFrame | None = None
        self._result: dict[str, Any] | None = None
        self._worker: _AnalyzeReAcceptedWorker | None = None
        self._dirty = False
        self._rerun_pending = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(10)

        # Header & action buttons
        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Re-Accepted Cancelled Offers")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E2226;")
        self.lbl_rule = QLabel(
            "Identifies unique cases where an offer cancellation ('O_Cancelled') is "
            "followed at a strictly later timestamp by an offer acceptance ('O_Accepted') "
            "within the same case, whether adjacent or separated by intermediate events."
        )
        self.lbl_rule.setWordWrap(True)
        self.lbl_rule.setStyleSheet("color: #5E666E; font-size: 11px;")
        title_col.addWidget(lbl_title)
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

        self.btn_reset = QPushButton("Reset Filter")
        self.btn_reset.setObjectName("toolbarBtn")
        self.btn_reset.clicked.connect(self._reset_view)
        hdr.addWidget(self.btn_reset)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("toolbarBtn")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(lambda: self.export_results())
        hdr.addWidget(self.btn_export)
        root.addLayout(hdr)

        # Warnings banner
        self.lbl_warnings = QLabel("")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet(
            "background: #FFF8E5; border: 1px solid #E5C365; "
            "border-radius: 4px; padding: 5px 8px; color: #664D03;"
        )
        self.lbl_warnings.hide()
        root.addWidget(self.lbl_warnings)

        # Top Disco Dark Chart + Right KPI Panel
        top_card = QFrame()
        top_card.setObjectName("discoWhitePanel")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(12, 10, 14, 10)
        top_layout.setSpacing(14)

        self.chart = DiscoDarkChart(top_card)
        self.chart.setFixedHeight(150)
        top_layout.addWidget(self.chart, 1)

        self.kpi_panel = DiscoKpiPanel(
            [
                ("matched", "Re-accepted cases"),
                ("total_log", "Total cases in log"),
                ("percentage", "Match rate"),
                ("mean_turnaround", "Mean turnaround"),
                ("same_ts", "Equal-timestamp ties"),
            ],
            top_card,
        )
        top_layout.addWidget(self.kpi_panel)
        root.addWidget(top_card)

        # Search + Open in Cases toolbar
        bar = QHBoxLayout()
        self.lbl_status = QLabel("Import an XES event log to detect re-accepted cancelled offers.")
        self.lbl_status.setStyleSheet("font-weight: 600; color: #495057;")
        bar.addWidget(self.lbl_status, 1)

        self.txt_search = make_disco_search("Search case ID...")
        self.txt_search.setFixedWidth(210)
        self.txt_search.textChanged.connect(self._apply_search)
        bar.addWidget(self.txt_search)

        self.btn_open_explorer = QPushButton("Open in Cases")
        self.btn_open_explorer.setObjectName("primaryActionBtn")
        self.btn_open_explorer.setEnabled(False)
        self.btn_open_explorer.clicked.connect(self._on_open_case_clicked)
        bar.addWidget(self.btn_open_explorer)
        root.addLayout(bar)

        # Horizontal splitter: Matched Cases Table (left) | Step Flow / Evidence Table (right)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.case_model = _ReAcceptedCaseModel(self)
        self.case_proxy = QSortFilterProxyModel(self)
        self.case_proxy.setSourceModel(self.case_model)
        self.case_proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.case_proxy.setFilterKeyColumn(0)
        self.case_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.case_table = style_disco_table(QTableView())
        self.case_table.setModel(self.case_proxy)
        self.case_table.setSortingEnabled(True)
        self.case_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        bar_delegate = DiscoBarDelegate(
            self.case_model.max_for_column, parent=self.case_table
        )
        self.case_table.setItemDelegateForColumn(3, bar_delegate)
        self.case_table.setItemDelegateForColumn(5, bar_delegate)
        self.case_table.selectionModel().selectionChanged.connect(
            self._on_case_selection_changed
        )
        self.case_table.doubleClicked.connect(
            lambda _idx: self._on_open_case_clicked()
        )
        splitter.addWidget(self.case_table)

        # Right panel: Evidence Flow | Table
        right_panel = QWidget(splitter)
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(8, 0, 0, 0)
        r_layout.setSpacing(6)

        ev_hdr = QHBoxLayout()
        self.lbl_evidence_title = QLabel("Cancellation → Acceptance Excerpt")
        self.lbl_evidence_title.setStyleSheet("font-weight: 700; color: #3A4046;")
        ev_hdr.addWidget(self.lbl_evidence_title, 1)

        self.ev_toggle = DiscoSegmentedToggle([("flow", "Flow"), ("table", "Table")])
        self.ev_toggle.changed.connect(
            lambda k: self.ev_stack.setCurrentIndex(1 if k == "table" else 0)
        )
        ev_hdr.addWidget(self.ev_toggle)
        r_layout.addLayout(ev_hdr)

        self.ev_stack = QStackedWidget(right_panel)
        self.ev_graph = DiscoTraceGraphWidget(self.ev_stack)
        self.ev_stack.addWidget(self.ev_graph)

        self.evidence_model = _EvidenceTableModel(self)
        self.evidence_table = style_disco_table(QTableView())
        self.evidence_table.setModel(self.evidence_model)
        self.ev_stack.addWidget(self.evidence_table)

        r_layout.addWidget(self.ev_stack, 1)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 5)
        root.addWidget(splitter, 1)

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
            self.lbl_status.setText("No active dataset to analyze.")
            return
        df_ref = self.event_df
        self._dirty = False
        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Scanning cases for O_Cancelled followed by O_Accepted…")

        GLOBAL_TASK_SCHEDULER.submit(
            "reaccepted_1122",
            lambda: analyze_exercise_1122(df_ref),
            self._on_completed,
            self._on_failed,
            high_priority=True,
        )

    def get_result(self) -> dict[str, Any] | None:
        return self._result

    def export_results(self, file_path: str | Path | None = None) -> Path | None:
        if self._result is None:
            self.lbl_status.setText("Run the analysis first before exporting.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Export Re-Accepted Cancelled Offers to CSV",
                "reaccepted_cancelled_offers.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved_path = export_analysis_result_to_csv(self._result, target_path)
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"CSV export failed: {exc}")
            QMessageBox.warning(self, "CSV Export Failed", str(exc))
            return None

        self.lbl_status.setText(f"Exported results to {saved_path}")
        return saved_path

    # ------------------------------------------------------------ slots
    def _on_completed(self, result: dict[str, Any]) -> None:
        self.progress.hide()
        self.btn_run.setEnabled(True)

        self._result = result
        details = result.get("details", [])
        matched = int(result.get("total_cases", 0))
        total_log = int(result.get("total_cases_in_log", 0))
        pct = (matched / total_log * 100.0) if total_log > 0 else 0.0
        same_ts_count = len(result.get("same_timestamp_cases", []))

        secs_list = [float(d.get("time_between_seconds") or 0.0) for d in details]
        mean_sec = (sum(secs_list) / len(secs_list)) if secs_list else None

        self.kpi_panel.set_value("matched", f"{matched:,}")
        self.kpi_panel.set_value("total_log", f"{total_log:,}")
        self.kpi_panel.set_value("percentage", f"{pct:.2f}%")
        self.kpi_panel.set_value("mean_turnaround", format_human_duration(mean_sec))
        self.kpi_panel.set_value("same_ts", f"{same_ts_count:,}")

        if secs_list:
            days_s = pd.Series([s / 86400.0 for s in secs_list])
            if days_s.nunique() > 1:
                bins = pd.cut(days_s, bins=min(36, max(2, len(days_s))))
                hist = bins.value_counts().sort_index()
                self.chart.set_series(
                    [float(v) for v in hist.values],
                    [f"{days_s.min():.1f} d", f"{days_s.max():.1f} d"],
                    kind="bars",
                    x_caption="Turnaround time from O_Cancelled to O_Accepted (days)",
                    y_caption="Cases",
                )
            else:
                self.chart.set_series(
                    [float(len(days_s))],
                    [format_human_duration(secs_list[0])],
                    kind="bars",
                    x_caption="Turnaround time",
                    y_caption="Cases",
                )
        else:
            self.chart.clear_chart("No re-accepted cancelled offers found in this log")

        warnings = result.get("warnings") or []
        if warnings:
            self.lbl_warnings.setText("Notes:  " + "  ·  ".join(warnings))
            self.lbl_warnings.show()
        else:
            self.lbl_warnings.hide()

        self.case_model.set_rows(details)
        self.evidence_model.set_events([])
        self.ev_graph.set_events([])
        self.btn_export.setEnabled(True)
        self._update_count()

        if matched > 0:
            self.case_table.selectRow(0)

        self.result_ready.emit(result)

    def _on_failed(self, message: str) -> None:
        self.progress.hide()
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"Analysis failed: {message}")

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.progress.hide()
        self.btn_run.setEnabled(True)
        if self._rerun_pending:
            self._rerun_pending = False
            if self.event_df is not None and not self.event_df.empty:
                self.run_analysis()

    def _on_case_selection_changed(self) -> None:
        row_data = self._selected_case_row()
        if row_data is None:
            self.btn_open_explorer.setEnabled(False)
            self.evidence_model.set_events([])
            self.ev_graph.set_events([])
            self.lbl_evidence_title.setText("Cancellation → Acceptance Excerpt")
            return

        self.btn_open_explorer.setEnabled(True)
        cid = str(row_data.get("case_id", ""))
        excerpt = list(
            row_data.get("timeline_excerpt") or row_data.get("evidence_events") or []
        )
        between = int(row_data.get("events_between_count", 0))
        delta = format_human_duration(row_data.get("time_between_seconds"))
        self.lbl_evidence_title.setText(
            f"{cid}  ·  {between} intermediate step(s)  ·  {delta}"
        )
        self.evidence_model.set_events(excerpt)

        # Populate step-by-step deltas for DiscoTraceGraphWidget
        graph_events = []
        prev_ts = None
        for ev in excerpt:
            ev_copy = dict(ev)
            ts_raw = ev_copy.get("timestamp")
            delta_str = ""
            if ts_raw is not None:
                cur_ts = pd.to_datetime(ts_raw, errors="coerce", utc=True)
                if prev_ts is not None and pd.notna(cur_ts) and pd.notna(prev_ts):
                    sec = max(0.0, float((cur_ts - prev_ts).total_seconds()))
                    delta_str = format_human_duration(sec)
                prev_ts = cur_ts
            ev_copy["delta_from_prev_display"] = delta_str
            graph_events.append(ev_copy)

        self.ev_graph.set_events(
            graph_events,
            highlight_activities=[CANCELLED_ACTIVITY, ACCEPTED_ACTIVITY],
        )

    def _selected_case_row(self) -> dict[str, Any] | None:
        selection = self.case_table.selectionModel().selectedRows()
        if not selection:
            return None
        source_index = self.case_proxy.mapToSource(selection[0])
        return self.case_model.row_at(source_index.row())

    def _on_open_case_clicked(self) -> None:
        row_data = self._selected_case_row()
        if row_data is None:
            return
        cid = str(row_data["case_id"])
        self.open_case_requested.emit(cid)
        self.case_selected.emit(cid)

    def _apply_search(self, text: str) -> None:
        self.case_proxy.setFilterFixedString(text.strip())
        self._update_count()

    def _update_count(self) -> None:
        total = self.case_model.rowCount()
        shown = self.case_proxy.rowCount()
        self.lbl_status.setText(
            f"Showing {shown:,} of {total:,} re-accepted cases"
            if total
            else "0 re-accepted cancelled offers matched"
        )

    def _reset_view(self) -> None:
        self.txt_search.clear()
        self.case_table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self._update_count()

    def _clear_view(self) -> None:
        self.kpi_panel.reset()
        self.chart.clear_chart()
        self.lbl_warnings.hide()
        self.case_model.set_rows([])
        self.evidence_model.set_events([])
        self.ev_graph.set_events([])
        self.lbl_evidence_title.setText("Cancellation → Acceptance Excerpt")
        self.btn_open_explorer.setEnabled(False)
        self.btn_export.setEnabled(False)


__all__ = ["Exercise1122Page"]
