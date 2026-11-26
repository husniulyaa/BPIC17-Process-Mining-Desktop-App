"""Fluxicon Disco-inspired Repeated Fraud Assessment page (F04).

Provides ``BaseExercisePage`` (shared by Fraud Rework & Same-Officer Fraud
pages) and ``Exercise1115Page``, wrapping ``analysis.exercise_1115`` without
modifying the underlying analysis module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtWidgets import (
    QApplication,
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

from analysis.exercise_1115 import analyze_exercise_1115
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
from utils.exporter import export_analysis_result_to_csv


class AnalysisWorker(QObject):
    """Background worker executing an exercise analysis function off the UI thread."""

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        analyzer_fn: Callable[[pd.DataFrame], dict[str, Any]],
        event_df: pd.DataFrame,
    ) -> None:
        super().__init__()
        self._analyzer_fn = analyzer_fn
        self._event_df = event_df

    def run(self) -> None:
        try:
            result = self._analyzer_fn(self._event_df)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Analysis error: {exc}")


class _FraudCaseTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str], metric_col: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._headers = list(headers)
        self._metric_col = metric_col
        self._rows: list[tuple[list[Any], dict[str, Any]]] = []
        self._max_metric = 1.0

    def set_rows(self, rows: list[tuple[list[Any], dict[str, Any]]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        vals = []
        for cells, _detail in rows:
            if 0 <= self._metric_col < len(cells):
                try:
                    vals.append(float(cells[self._metric_col]))
                except (TypeError, ValueError):
                    pass
        self._max_metric = max(vals, default=1.0) or 1.0
        self.endResetModel()

    def max_for_column(self, col: int) -> float:
        return self._max_metric if col == self._metric_col else 0.0

    def detail_at(self, row_idx: int) -> dict[str, Any] | None:
        if 0 <= row_idx < len(self._rows):
            return self._rows[row_idx][1]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        cells, _detail = self._rows[index.row()]
        val = cells[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{int(val):,}" if isinstance(val, int) else str(val)
        if role == Qt.ItemDataRole.UserRole:
            return val
        return None


class _FraudEvidenceTableModel(QAbstractTableModel):
    HEADERS = ("Step", "Timestamp (UTC)", "Activity", "Lifecycle", "Resource", "Event ID")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, Any]] = []

    def set_items(self, items: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._items)

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
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        ev = self._items[index.row()]
        col = index.column()
        if col == 0:
            return str(index.row() + 1)
        if col == 1:
            return str(ev.get("timestamp") or "—")
        if col == 2:
            return str(ev.get("activity") or "—")
        if col == 3:
            return str(ev.get("lifecycle") or "—")
        if col == 4:
            return str(ev.get("resource") or "—")
        return str(ev["EventID"]) if ev.get("EventID") is not None else "—"


class BaseExercisePage(QWidget):
    """Fluxicon Disco-styled base page for Fraud Assessment rework analyses."""

    case_selected = Signal(str)
    open_case_requested = Signal(str)
    result_ready = Signal(dict)

    def __init__(
        self,
        title: str,
        rule_description: str,
        analyzer_fn: Callable[[pd.DataFrame], dict[str, Any]],
        case_headers: list[str],
        *,
        metric_key: str = "complete_count",
        export_slug: str = "fraud_assessment_rework",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title_text = title
        self._rule_text = rule_description
        self._analyzer_fn = analyzer_fn
        self._case_headers = case_headers
        self._metric_key = metric_key
        self._export_slug = export_slug

        self._event_df: pd.DataFrame | None = None
        self._last_result: dict[str, Any] | None = None
        self._details: list[dict[str, Any]] = []
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None
        self._dirty = False
        self._rerun_pending = False

        self._init_ui()
        self._reset_view()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(10)

        # Header & controls
        hdr = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel(self._title_text)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #1E2226;")
        self.rule_label = QLabel(self._rule_text)
        self.rule_label.setWordWrap(True)
        self.rule_label.setStyleSheet("color: #5E666E; font-size: 11px;")
        title_col.addWidget(self.title_label)
        title_col.addWidget(self.rule_label)
        hdr.addLayout(title_col, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        hdr.addWidget(self.progress)

        self.run_button = QPushButton("Recalculate")
        self.run_button.setObjectName("toolbarBtn")
        self.run_button.clicked.connect(self._on_run_clicked)
        hdr.addWidget(self.run_button)

        self.reset_button = QPushButton("Reset Filter")
        self.reset_button.setObjectName("toolbarBtn")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        hdr.addWidget(self.reset_button)

        self.export_button = QPushButton("Export CSV")
        self.export_button.setObjectName("toolbarBtn")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(lambda: self.export_results())
        hdr.addWidget(self.export_button)

        root.addLayout(hdr)

        # Warning banner
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            "background: #FFF8E5; border: 1px solid #E5C365; "
            "border-radius: 4px; padding: 5px 8px; color: #664D03;"
        )
        self.warning_label.hide()
        root.addWidget(self.warning_label)

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
                ("matched", "Flagged cases"),
                ("total_log", "Total cases in log"),
                ("rate", "Flagged share"),
                ("max_cnt", "Peak completions"),
            ],
            top_card,
        )
        top_layout.addWidget(self.kpi_panel)
        root.addWidget(top_card)

        # Search + Open in Cases toolbar
        action_row = QHBoxLayout()
        self.status_label = QLabel("Import an XES event log to run fraud rework analysis.")
        self.status_label.setStyleSheet("font-weight: 600; color: #495057;")
        action_row.addWidget(self.status_label, 1)

        self.txt_search = make_disco_search("Search case ID...")
        self.txt_search.setFixedWidth(210)
        self.txt_search.textChanged.connect(self._apply_search)
        action_row.addWidget(self.txt_search)

        self.btn_open_explorer = QPushButton("Open in Cases")
        self.btn_open_explorer.setObjectName("primaryActionBtn")
        self.btn_open_explorer.setEnabled(False)
        self.btn_open_explorer.clicked.connect(self._open_selected_in_explorer)
        action_row.addWidget(self.btn_open_explorer)
        root.addLayout(action_row)

        # Bottom splitter: Left case table | Right evidence Flow/Table
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        metric_col = len(self._case_headers) - 1
        self.case_model = _FraudCaseTableModel(self._case_headers, metric_col, self)
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
        self.case_table.setItemDelegateForColumn(metric_col, bar_delegate)
        self.case_table.selectionModel().selectionChanged.connect(
            self._on_case_row_selected
        )
        self.case_table.doubleClicked.connect(
            lambda _idx: self._open_selected_in_explorer()
        )
        splitter.addWidget(self.case_table)

        # Right evidence pane with Disco Flow | Table toggle
        ev_pane = QWidget(splitter)
        ev_layout = QVBoxLayout(ev_pane)
        ev_layout.setContentsMargins(8, 0, 0, 0)
        ev_layout.setSpacing(6)

        ev_hdr = QHBoxLayout()
        self.lbl_ev_title = QLabel("Matching Fraud Assessment Evidence")
        self.lbl_ev_title.setStyleSheet("font-weight: 700; color: #3A4046;")
        ev_hdr.addWidget(self.lbl_ev_title, 1)

        self.ev_toggle = DiscoSegmentedToggle([("flow", "Flow"), ("table", "Table")])
        self.ev_toggle.changed.connect(
            lambda k: self.ev_stack.setCurrentIndex(1 if k == "table" else 0)
        )
        ev_hdr.addWidget(self.ev_toggle)
        ev_layout.addLayout(ev_hdr)

        self.ev_stack = QStackedWidget(ev_pane)
        self.ev_graph = DiscoTraceGraphWidget(self.ev_stack)
        self.ev_stack.addWidget(self.ev_graph)

        self.evidence_model = _FraudEvidenceTableModel(self)
        self.evidence_table = style_disco_table(QTableView())
        self.evidence_table.setModel(self.evidence_model)
        self.ev_stack.addWidget(self.evidence_table)

        ev_layout.addWidget(self.ev_stack, 1)
        splitter.addWidget(ev_pane)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        self._event_df = event_df
        self._reset_view()
        if event_df is None or event_df.empty:
            self._dirty = False
            self._rerun_pending = self._thread is not None
            return

        self._dirty = True
        if self.isVisible():
            self._on_run_clicked()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty and self._event_df is not None and not self._event_df.empty:
            self._on_run_clicked()

    def export_results(self, file_path: str | Path | None = None) -> Path | None:
        if self._last_result is None:
            return None
        target = file_path
        if target is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {self._title_text} to CSV",
                f"{self._export_slug}.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target = selected
        try:
            saved = export_analysis_result_to_csv(self._last_result, target)
            self.status_label.setText(f"Exported results to {saved}")
            return saved
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export Failed", str(exc))
            return None

    # ------------------------------------------------------------ internals
    def _reset_view(self) -> None:
        self._last_result = None
        self._details = []
        self.case_model.set_rows([])
        self.evidence_model.set_items([])
        self.ev_graph.set_events([])
        self.kpi_panel.reset()
        self.chart.clear_chart()
        self.warning_label.hide()
        self.export_button.setEnabled(False)
        self.btn_open_explorer.setEnabled(False)

        if self._event_df is None or self._event_df.empty:
            self.status_label.setText("No active dataset loaded.")
            self.run_button.setEnabled(False)
        else:
            self.status_label.setText(
                f"Dataset ready ({len(self._event_df):,} events)."
            )
            self.run_button.setEnabled(self._thread is None)

    def _on_reset_clicked(self) -> None:
        self.txt_search.clear()
        self.case_table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)

    def _on_run_clicked(self) -> None:
        if self._event_df is None or self._event_df.empty:
            return
        df_ref = self._event_df
        fn_ref = self._analyzer_fn
        self._dirty = False
        self.run_button.setEnabled(False)
        self.progress.show()
        self.status_label.setText("Scanning fraud assessment lifecycle transitions…")

        GLOBAL_TASK_SCHEDULER.submit(
            f"fraud_{self._export_slug}",
            lambda: fn_ref(df_ref),
            self._on_analysis_finished,
            self._on_analysis_failed,
            high_priority=True,
        )

    def _on_analysis_failed(self, error_message: str) -> None:
        self.progress.hide()
        self.run_button.setEnabled(
            self._event_df is not None and not self._event_df.empty
        )
        self.status_label.setText(error_message)

    def _on_analysis_finished(self, result: dict[str, Any]) -> None:
        self.progress.hide()
        self.run_button.setEnabled(
            self._event_df is not None and not self._event_df.empty
        )
        self._last_result = result
        self._details = list(result.get("details", []))

        total_cases = int(result.get("total_cases", 0))
        total_in_log = int(result.get("total_cases_in_log", 0))
        rate = (total_cases / total_in_log * 100.0) if total_in_log > 0 else 0.0
        counts = [int(d.get(self._metric_key, 0)) for d in self._details]
        peak = max(counts, default=0)

        self.kpi_panel.set_value("matched", f"{total_cases:,}")
        self.kpi_panel.set_value("total_log", f"{total_in_log:,}")
        self.kpi_panel.set_value("rate", f"{rate:.2f}%")
        self.kpi_panel.set_value("max_cnt", f"{peak:,}" if peak else "0")

        warnings = result.get("warnings", [])
        if warnings:
            self.warning_label.setText("Note: " + " | ".join(str(w) for w in warnings))
            self.warning_label.show()
        else:
            self.warning_label.hide()

        # Distribution chart of completion counts
        if counts:
            dist = pd.Series(counts).value_counts().sort_index()
            self.chart.set_series(
                [float(v) for v in dist.values],
                [f"{int(dist.index.min())}×", f"{int(dist.index.max())}×"],
                kind="bars",
                x_caption="Completed fraud assessments per flagged case",
                y_caption="Cases",
            )
        else:
            self.chart.clear_chart("No cases met the fraud rework threshold")

        self.case_model.set_rows(self._build_case_rows(self._details))
        self.export_button.setEnabled(True)
        self._update_status_count()

        if self.case_proxy.rowCount() > 0:
            self.case_table.selectRow(0)

        self.result_ready.emit(result)

    def _build_case_rows(
        self,
        details: list[dict[str, Any]],
    ) -> list[tuple[list[Any], dict[str, Any]]]:
        raise NotImplementedError

    def _selected_detail(self) -> dict[str, Any] | None:
        sel = self.case_table.selectionModel().selectedRows()
        if not sel:
            return None
        src_row = self.case_proxy.mapToSource(sel[0]).row()
        return self.case_model.detail_at(src_row)

    def _on_case_row_selected(self) -> None:
        detail = self._selected_detail()
        if detail is None:
            self.btn_open_explorer.setEnabled(False)
            self.evidence_model.set_items([])
            self.ev_graph.set_events([])
            self.lbl_ev_title.setText("Matching Fraud Assessment Evidence")
            return

        self.btn_open_explorer.setEnabled(True)
        cid = str(detail.get("case_id", ""))
        evidence = list(detail.get("evidence", []))
        self.lbl_ev_title.setText(f"Fraud Assessment Evidence — {cid} ({len(evidence)} events)")
        self.evidence_model.set_items(evidence)

        # Build step cards for DiscoTraceGraphWidget
        graph_events = []
        prev_ts = None
        for idx, item in enumerate(evidence):
            ts_raw = item.get("timestamp")
            delta_txt = ""
            if ts_raw is not None:
                cur_ts = pd.to_datetime(ts_raw, errors="coerce", utc=True)
                if prev_ts is not None and pd.notna(cur_ts) and pd.notna(prev_ts):
                    sec = max(0.0, float((cur_ts - prev_ts).total_seconds()))
                    from utils.case_timeline import format_human_duration

                    delta_txt = format_human_duration(sec)
                prev_ts = cur_ts
            graph_events.append(
                {
                    "step": idx + 1,
                    "activity": item.get("activity") or "W_Assess Potential Fraud",
                    "timestamp": ts_raw,
                    "resource": item.get("resource"),
                    "lifecycle": item.get("lifecycle"),
                    "delta_from_prev_display": delta_txt,
                }
            )
        self.ev_graph.set_events(
            graph_events, highlight_activities=["W_Assess Potential Fraud"]
        )
        self.case_selected.emit(cid)

    def _open_selected_in_explorer(self) -> None:
        detail = self._selected_detail()
        if detail is None:
            return
        cid = str(detail.get("case_id", ""))
        if cid:
            self.open_case_requested.emit(cid)

    def _apply_search(self, text: str) -> None:
        self.case_proxy.setFilterFixedString(text.strip())
        self._update_status_count()

    def _update_status_count(self) -> None:
        total = self.case_model.rowCount()
        shown = self.case_proxy.rowCount()
        self.status_label.setText(
            f"Showing {shown:,} of {total:,} flagged cases"
            if total
            else "0 cases flagged under this fraud assessment rule"
        )


class Exercise1115Page(BaseExercisePage):
    """Repeated Fraud Assessment page (cases with >= 2 completed fraud checks)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Repeated Fraud Assessment",
            rule_description=(
                "Identifies unique cases where 'W_Assess Potential Fraud' reached "
                "lifecycle 'complete' at least twice within the same case."
            ),
            analyzer_fn=analyze_exercise_1115,
            case_headers=["Case ID", "Completed Assessments"],
            metric_key="complete_count",
            export_slug="repeated_fraud_assessment",
            parent=parent,
        )

    def _build_case_rows(
        self,
        details: list[dict[str, Any]],
    ) -> list[tuple[list[Any], dict[str, Any]]]:
        return [
            ([str(item.get("case_id", "")), int(item.get("complete_count", 0))], item)
            for item in details
        ]


def _build_demo_dataframe() -> pd.DataFrame:
    csv_path = os.environ.get("BPIC17_CSV_PATH", "")
    if csv_path and os.path.isfile(csv_path):
        return pd.read_csv(csv_path)

    return pd.DataFrame(
        [
            {
                "case:concept:name": "Demo_Case_01",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_1",
                "EventID": "E_101",
            },
            {
                "case:concept:name": "Demo_Case_01",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_2",
                "EventID": "E_102",
            },
        ]
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = Exercise1115Page()
    page.resize(1040, 620)
    page.show()
    page.set_event_data(_build_demo_dataframe())
    sys.exit(app.exec())
