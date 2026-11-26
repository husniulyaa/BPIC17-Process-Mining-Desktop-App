"""Fluxicon Disco-inspired Case Explorer, Variants & Trace Graph page (F07).

Features:
- Dual left master-detail columns: Variants (ranked by frequency) + Cases
- Dark charcoal case event profile chart + right KPI panel
- Segmented Graph | Table toggle:
    * Graph: Disco's step-by-step vertical rounded flow cards with duration pills
    * Table: Full sortable/searchable event table
- Event Attribute Inspector showing all source XES attributes
- CSV export for individual case timelines and filtered case summaries
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from PySide6.QtCore import (
    QAbstractListModel,
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
    QListView,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ui.disco_widgets import (
    DiscoDarkChart,
    DiscoKpiPanel,
    DiscoSegmentedToggle,
    DiscoSidebarList,
    DiscoTraceGraphWidget,
    _SidebarItemDelegate,
    make_disco_search,
    style_disco_table,
)
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from utils.case_timeline import (
    build_case_row_index,
    build_case_summaries_and_variants,
    filter_case_summaries,
    get_case_detail,
)
from utils.exporter import (
    export_case_summaries_to_csv,
    export_case_timeline_to_csv,
    sanitize_filename_component,
)


class _CaseIndexWorker(QThread):
    """Background worker indexing case summaries and process variants."""

    completed = Signal(list, list)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            summaries, variants = build_case_summaries_and_variants(self._event_df)
            self.completed.emit(summaries, variants)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _FastCaseListModel(QAbstractListModel):
    """Virtualized list model rendering 30k+ cases effortlessly with Disco styling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def case_id_at(self, row_index: int) -> str | None:
        if 0 <= row_index < len(self._rows):
            return str(self._rows[row_index]["case_id"])
        return None

    def summary_at(self, row_index: int) -> dict[str, Any] | None:
        if 0 <= row_index < len(self._rows):
            return self._rows[row_index]
        return None

    def find_row(self, case_id: str) -> int:
        target = str(case_id)
        for idx, row in enumerate(self._rows):
            if str(row.get("case_id")) == target:
                return idx
        return -1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, _SidebarItemDelegate.ROLE_TITLE):
            return str(row.get("case_id", ""))
        if role == _SidebarItemDelegate.ROLE_SUBTITLE:
            return f"{int(row.get('event_count', 0)):,} events  ·  {row.get('duration_human', '—')}"
        if role == _SidebarItemDelegate.ROLE_KEY:
            return str(row.get("case_id", ""))
        return None


class _TimelineTableModel(QAbstractTableModel):
    """Table model for the Table view of a single case's event trace."""

    HEADERS = (
        "Step",
        "Activity",
        "Timestamp (UTC)",
        "Waiting / Delta",
        "Elapsed",
        "Resource",
        "Lifecycle",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: list[dict[str, Any]] = []
        self._has_lifecycle = False
        self._has_resource = False
        self._highlights: set[str] = set()

    def set_timeline(
        self,
        events: list[dict[str, Any]],
        *,
        has_lifecycle: bool,
        has_resource: bool,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        self.beginResetModel()
        self._events = list(events)
        self._has_lifecycle = has_lifecycle
        self._has_resource = has_resource
        self._highlights = {
            str(a).strip() for a in (highlight_activities or []) if str(a).strip()
        }
        self.endResetModel()

    def event_at(self, row_index: int) -> dict[str, Any] | None:
        if 0 <= row_index < len(self._events):
            return self._events[row_index]
        return None

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
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None
        ev = self._events[index.row()]
        col = index.column()
        activity = str(ev.get("activity", ""))

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(ev.get("step", ""))
            if col == 1:
                return activity
            if col == 2:
                return str(ev.get("timestamp") or "NaT")
            if col == 3:
                return str(ev.get("delta_from_prev_display", "—"))
            if col == 4:
                return str(ev.get("elapsed_from_start_display", "—"))
            if col == 5:
                return (
                    "(unavailable)"
                    if not self._has_resource
                    else str(ev.get("resource") or "—")
                )
            if col == 6:
                return (
                    "(unavailable)"
                    if not self._has_lifecycle
                    else str(ev.get("lifecycle") or "—")
                )

        if role == Qt.ItemDataRole.BackgroundRole:
            if activity == "O_Cancelled":
                return QBrush(QColor("#FDECEC"))
            if activity == "O_Accepted":
                return QBrush(QColor("#E8F7EE"))
            if activity in self._highlights:
                return QBrush(QColor("#FFF3CD"))

        if role == Qt.ItemDataRole.TextAlignmentRole and col == 0:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


class CaseExplorerPage(QWidget):
    """Fluxicon Disco-inspired Cases & Variant Inspector page (F07)."""

    case_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cases")

        self.event_df: pd.DataFrame | None = None
        self._all_summaries: list[dict[str, Any]] = []
        self._all_variants: list[dict[str, Any]] = []
        self._summary_map: dict[str, dict[str, Any]] = {}
        self._allowed_case_ids: set[str] | None = None
        self._filter_label: str = ""
        self._selected_variant_id: str = "__ALL__"
        self._current_case_id: str | None = None
        self._current_detail: dict[str, Any] | None = None
        self._pending_case_id: str | None = None
        self._pending_highlights: list[str] | None = None
        self._worker: _CaseIndexWorker | None = None
        self._dirty = False
        self._reindex_pending = False

        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Sub-toolbar (status left, search & export actions right)
        subbar = QFrame()
        subbar.setObjectName("discoSubBar")
        sub_layout = QHBoxLayout(subbar)
        sub_layout.setContentsMargins(14, 5, 14, 5)
        sub_layout.setSpacing(10)

        self.lbl_status = QLabel("Import an XES event log to inspect individual cases and variants.")
        self.lbl_status.setStyleSheet("color: #555D65;")
        sub_layout.addWidget(self.lbl_status, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        sub_layout.addWidget(self.progress)

        self.btn_clear_filter = QPushButton("Show All Cases")
        self.btn_clear_filter.setObjectName("toolbarBtn")
        self.btn_clear_filter.clicked.connect(self.clear_case_filter)
        self.btn_clear_filter.hide()
        sub_layout.addWidget(self.btn_clear_filter)

        self.btn_export_case = QPushButton("Export Case Timeline (CSV)")
        self.btn_export_case.setObjectName("primaryActionBtn")
        self.btn_export_case.setEnabled(False)
        self.btn_export_case.clicked.connect(lambda: self.export_current_case_csv())
        sub_layout.addWidget(self.btn_export_case)

        self.btn_export_list = QPushButton("Export Case List (CSV)")
        self.btn_export_list.setObjectName("toolbarBtn")
        self.btn_export_list.setEnabled(False)
        self.btn_export_list.clicked.connect(lambda: self.export_case_list_csv())
        sub_layout.addWidget(self.btn_export_list)

        self.txt_case_search = make_disco_search("Search case ID...")
        self.txt_case_search.setFixedWidth(210)
        self.txt_case_search.textChanged.connect(self._refresh_case_list)
        sub_layout.addWidget(self.txt_case_search)

        outer.addWidget(subbar)

        # Main horizontal splitter: Variants | Cases | Case Detail
        main_split = QSplitter(Qt.Orientation.Horizontal, self)

        # Column 1: Variants list (like Disco Screenshot 1)
        self.variant_sidebar = DiscoSidebarList("Variants (0)", main_split)
        self.variant_sidebar.setMinimumWidth(185)
        self.variant_sidebar.setMaximumWidth(250)
        self.variant_sidebar.item_selected.connect(self._on_variant_selected)
        main_split.addWidget(self.variant_sidebar)

        # Column 2: Virtualized Cases list
        cases_col = QWidget(main_split)
        cases_col.setMinimumWidth(215)
        cases_col.setMaximumWidth(290)
        cases_layout = QVBoxLayout(cases_col)
        cases_layout.setContentsMargins(0, 0, 0, 0)
        cases_layout.setSpacing(0)

        self.lbl_cases_header = QLabel("Cases (0)")
        self.lbl_cases_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cases_header.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #F3F3F3,stop:1 #DFDFDF);"
            "border: 1px solid #C5C5C5; border-bottom: none;"
            "padding: 4px 8px; font-size: 11px; font-weight: 600; color: #555555;"
        )
        cases_layout.addWidget(self.lbl_cases_header)

        self.case_model = _FastCaseListModel(self)
        self.case_list = QListView()
        self.case_list.setModel(self.case_model)
        self.case_list.setItemDelegate(_SidebarItemDelegate(self.case_list))
        self.case_list.setUniformItemSizes(True)
        self.case_list.setMouseTracking(True)
        self.case_list.setStyleSheet(
            "QListView { background: #FFFFFF; border: 1px solid #C5C5C5; outline: none; }"
        )
        self.case_list.selectionModel().currentChanged.connect(
            self._on_case_index_selected
        )
        cases_layout.addWidget(self.case_list, 1)
        main_split.addWidget(cases_col)

        # Column 3: Right Case Inspector (Header + Dark Chart & KPIs + Graph|Table + Attributes)
        detail_pane = QWidget(main_split)
        d_layout = QVBoxLayout(detail_pane)
        d_layout.setContentsMargins(18, 12, 18, 12)
        d_layout.setSpacing(10)

        # Case title banner
        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self.lbl_case_title = QLabel("No case selected")
        self.lbl_case_title.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #1E2226;"
        )
        self.lbl_case_subtitle = QLabel("Select a case from the left list to inspect its trace")
        self.lbl_case_subtitle.setStyleSheet("color: #6B727A; font-size: 11px;")
        title_col.addWidget(self.lbl_case_title)
        title_col.addWidget(self.lbl_case_subtitle)
        title_row.addLayout(title_col, 1)
        d_layout.addLayout(title_row)

        # Optional warning banner (invalid timestamps / missing optional attributes)
        self.lbl_case_note = QLabel("")
        self.lbl_case_note.setWordWrap(True)
        self.lbl_case_note.setStyleSheet(
            "background: #FFF8E5; border: 1px solid #E5C365; "
            "border-radius: 4px; padding: 5px 8px; color: #664D03;"
        )
        self.lbl_case_note.hide()
        d_layout.addWidget(self.lbl_case_note)

        # Dark charcoal event timeline profile + right KPIs
        top_card = QFrame()
        top_card.setObjectName("discoWhitePanel")
        top_card_layout = QHBoxLayout(top_card)
        top_card_layout.setContentsMargins(12, 10, 14, 10)
        top_card_layout.setSpacing(14)

        self.case_chart = DiscoDarkChart(top_card)
        self.case_chart.setFixedHeight(138)
        top_card_layout.addWidget(self.case_chart, 1)

        self.kpi_panel = DiscoKpiPanel(
            [
                ("events", "Events"),
                ("activities", "Unique activities"),
                ("start", "Start"),
                ("duration", "Duration"),
            ],
            top_card,
        )
        top_card_layout.addWidget(self.kpi_panel)
        d_layout.addWidget(top_card)

        # Centered Graph | Table segmented toggle + activity filter
        toggle_bar = QHBoxLayout()
        toggle_bar.addStretch(1)
        self.view_toggle = DiscoSegmentedToggle(
            [("graph", "Graph"), ("table", "Table")]
        )
        self.view_toggle.changed.connect(self._on_view_mode_changed)
        toggle_bar.addWidget(self.view_toggle)
        toggle_bar.addStretch(1)

        self.txt_activity_filter = make_disco_search("Filter activity in trace...")
        self.txt_activity_filter.setFixedWidth(190)
        self.txt_activity_filter.textChanged.connect(self._apply_activity_filter)
        self.txt_activity_filter.hide()
        toggle_bar.addWidget(self.txt_activity_filter)
        d_layout.addLayout(toggle_bar)

        # Vertical splitter: Trace View (Graph or Table) + Attribute Inspector
        trace_split = QSplitter(Qt.Orientation.Vertical, detail_pane)

        self.trace_stack = QStackedWidget(trace_split)
        self.graph_widget = DiscoTraceGraphWidget(self.trace_stack)
        self.graph_widget.step_clicked.connect(self._on_graph_step_clicked)
        self.trace_stack.addWidget(self.graph_widget)

        self.timeline_model = _TimelineTableModel(self)
        self.timeline_proxy = QSortFilterProxyModel(self)
        self.timeline_proxy.setSourceModel(self.timeline_model)
        self.timeline_proxy.setFilterKeyColumn(1)
        self.timeline_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.timeline_table = style_disco_table(QTableView())
        self.timeline_table.setModel(self.timeline_proxy)
        self.timeline_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.timeline_table.selectionModel().selectionChanged.connect(
            self._on_table_event_selected
        )
        self.trace_stack.addWidget(self.timeline_table)
        trace_split.addWidget(self.trace_stack)

        # Event raw XES attributes inspector
        attr_panel = QFrame(trace_split)
        attr_panel.setObjectName("discoWhitePanel")
        attr_layout = QVBoxLayout(attr_panel)
        attr_layout.setContentsMargins(10, 6, 10, 6)
        attr_layout.setSpacing(4)
        lbl_attr = QLabel("Selected Event Attributes (Source XES Traceability)")
        lbl_attr.setStyleSheet("font-size: 11px; font-weight: 700; color: #495057;")
        self.txt_event_inspector = QPlainTextEdit()
        self.txt_event_inspector.setReadOnly(True)
        self.txt_event_inspector.setMaximumHeight(115)
        self.txt_event_inspector.setStyleSheet(
            "QPlainTextEdit { background: #FBFDFE; border: 1px solid #DDE2E8; "
            "font-family: Consolas, monospace; font-size: 11px; }"
        )
        self.txt_event_inspector.setPlaceholderText(
            "Click any step card or table row to inspect all raw XES event attributes."
        )
        attr_layout.addWidget(lbl_attr)
        attr_layout.addWidget(self.txt_event_inspector)
        trace_split.addWidget(attr_panel)

        trace_split.setStretchFactor(0, 4)
        trace_split.setStretchFactor(1, 1)
        d_layout.addWidget(trace_split, 1)

        main_split.addWidget(detail_pane)
        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 1)
        main_split.setStretchFactor(2, 4)
        outer.addWidget(main_split, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        self.event_df = event_df
        self._all_summaries = []
        self._all_variants = []
        self._summary_map = {}
        self._case_row_index: dict[str, Any] = {}
        self._allowed_case_ids = None
        self._filter_label = ""
        self._selected_variant_id = "__ALL__"
        self._current_case_id = None
        self._current_detail = None
        self.btn_clear_filter.hide()
        self._clear_all()

        if event_df is None or event_df.empty:
            self._dirty = False
            self._indexing = False
            self.progress.hide()
            self.lbl_status.setText("No active dataset loaded.")
            return

        self._dirty = True
        self._indexing = False
        if self.isVisible():
            self._start_indexing()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty and self.event_df is not None and not self.event_df.empty:
            self._start_indexing()

    def select_case(
        self,
        case_id: str,
        highlight_activities: Sequence[str] | None = None,
    ) -> bool:
        """Jump directly to ``case_id`` (e.g. triggered from any analysis page)."""
        target = str(case_id).strip()
        if not target:
            return False

        if self.event_df is None or self.event_df.empty:
            self.lbl_status.setText("Dataset is not loaded.")
            return False

        if self._dirty and not getattr(self, "_indexing", False):
            self._pending_case_id = target
            self._pending_highlights = (
                list(highlight_activities) if highlight_activities else None
            )
            self._start_indexing()
            return True

        if getattr(self, "_indexing", False):
            self._pending_case_id = target
            self._pending_highlights = (
                list(highlight_activities) if highlight_activities else None
            )
            return True

        if self._allowed_case_ids is not None and target not in self._allowed_case_ids:
            self.clear_case_filter()

        if self._selected_variant_id != "__ALL__":
            self._selected_variant_id = "__ALL__"
            self.variant_sidebar.select_key("__ALL__", emit_signal=False)
            self._refresh_case_list()

        if self.txt_case_search.text().strip():
            self.txt_case_search.clear()

        row_idx_map = getattr(self, "_case_row_index", None) or None
        detail = get_case_detail(
            self.event_df,
            target,
            case_row_index=row_idx_map,
        )
        if not detail.get("found"):
            self.lbl_status.setText(f"Case '{target}' was not found in the active log.")
            return False

        self._display_case_detail(detail, highlight_activities=highlight_activities)

        row_idx = self.case_model.find_row(target)
        if row_idx >= 0:
            idx = self.case_model.index(row_idx, 0)
            self.case_list.selectionModel().blockSignals(True)
            try:
                self.case_list.setCurrentIndex(idx)
                self.case_list.scrollTo(idx)
            finally:
                self.case_list.selectionModel().blockSignals(False)

        self.case_selected.emit(target)
        return True

    def set_case_filter(
        self,
        case_ids: Sequence[str] | None,
        label: str = "",
    ) -> None:
        if case_ids is None:
            self.clear_case_filter()
            return
        self._allowed_case_ids = {str(cid) for cid in case_ids}
        self._filter_label = label.strip()
        self._selected_variant_id = "__ALL__"
        self.btn_clear_filter.show()
        self._populate_variants()
        self._refresh_case_list()

    def clear_case_filter(self) -> None:
        self._allowed_case_ids = None
        self._filter_label = ""
        self._selected_variant_id = "__ALL__"
        self.btn_clear_filter.hide()
        self._populate_variants()
        self._refresh_case_list()

    def export_current_case_csv(
        self,
        file_path: str | Path | None = None,
    ) -> Path | None:
        if self.event_df is None or not self._current_case_id:
            self.lbl_status.setText("Select a case first before exporting its timeline.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            safe_id = sanitize_filename_component(self._current_case_id)
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Export Case Timeline to CSV",
                f"case_{safe_id}_timeline.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved = export_case_timeline_to_csv(
                self.event_df,
                self._current_case_id,
                target_path,
            )
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Timeline export failed: {exc}")
            QMessageBox.warning(self, "Export Failed", str(exc))
            return None

        self.lbl_status.setText(
            f"Exported case '{self._current_case_id}' timeline to {saved}"
        )
        return saved

    def export_case_list_csv(
        self,
        file_path: str | Path | None = None,
    ) -> Path | None:
        visible_rows = self.case_model.rows()
        if not visible_rows:
            self.lbl_status.setText("No cases available to export.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Export Case Summaries to CSV",
                "case_summaries.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved = export_case_summaries_to_csv(visible_rows, target_path)
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Case list export failed: {exc}")
            QMessageBox.warning(self, "Export Failed", str(exc))
            return None

        self.lbl_status.setText(f"Exported {len(visible_rows):,} case summaries to {saved}")
        return saved

    # ------------------------------------------------------------ internal
    def _start_indexing(self) -> None:
        if self.event_df is None or self.event_df.empty:
            return
        df_ref = self.event_df
        self._dirty = False
        self._indexing = True
        self.progress.show()
        self.lbl_status.setText("Indexing cases and process variants…")

        def _compute_all() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
            row_idx = build_case_row_index(df_ref)
            summaries, variants = build_case_summaries_and_variants(df_ref)
            return summaries, variants, row_idx

        GLOBAL_TASK_SCHEDULER.submit(
            "case_explorer_index",
            _compute_all,
            lambda payload: self._on_index_completed(*payload),
            self._on_index_failed,
            high_priority=True,
        )

    def _on_index_completed(
        self,
        summaries: list[dict[str, Any]],
        variants: list[dict[str, Any]],
        row_idx: dict[str, Any],
    ) -> None:
        self._indexing = False
        self.progress.hide()
        self._all_summaries = summaries
        self._all_variants = variants
        self._summary_map = {s["case_id"]: s for s in summaries}
        self._case_row_index = row_idx

        self._populate_variants()
        self._refresh_case_list()
        self.lbl_status.setText(
            f"Indexed {len(summaries):,} cases across {len(variants):,} distinct variants."
        )

        if self._pending_case_id:
            cid = self._pending_case_id
            hl = self._pending_highlights
            self._pending_case_id = None
            self._pending_highlights = None
            self.select_case(cid, highlight_activities=hl)
        elif self.case_model.rowCount() > 0:
            first_idx = self.case_model.index(0, 0)
            self.case_list.setCurrentIndex(first_idx)

    def _on_index_failed(self, msg: str) -> None:
        self._indexing = False
        self.progress.hide()
        self.lbl_status.setText(f"Failed to index cases: {msg}")

    def _populate_variants(self) -> None:
        total_cases = len(self._all_summaries)
        all_title = (
            f"Filtered subset" if self._filter_label else "Complete log"
        )
        all_sub = (
            f"{len(self._allowed_case_ids):,} cases ({self._filter_label})"
            if self._allowed_case_ids is not None
            else f"All cases ({total_cases:,})"
        )
        items: list[tuple[str, str, str]] = [("__ALL__", all_title, all_sub)]
        # Show up to top 250 variants in sidebar so UI stays instantaneous even with 15k variants
        for v in self._all_variants[:250]:
            items.append(
                (
                    v["variant_id"],
                    v["label"],
                    f"{v['case_count']:,} cases ({v['percentage']:.2f}%)",
                )
            )
        self.variant_sidebar.set_header(f"Variants ({len(self._all_variants):,})")
        self.variant_sidebar.set_items(items, select_key=self._selected_variant_id)

    def _on_variant_selected(self, variant_key: str) -> None:
        self._selected_variant_id = variant_key
        self._refresh_case_list()
        if self.case_model.rowCount() > 0:
            self.case_list.setCurrentIndex(self.case_model.index(0, 0))

    def _refresh_case_list(self) -> None:
        filtered = filter_case_summaries(
            self._all_summaries,
            query=self.txt_case_search.text(),
            allowed_case_ids=self._allowed_case_ids,
            variant_id=self._selected_variant_id,
        )
        self.case_model.set_rows(filtered)
        self.btn_export_list.setEnabled(bool(filtered))
        self.lbl_cases_header.setText(f"Cases ({len(filtered):,})")

    def _on_case_index_selected(
        self,
        current: QModelIndex,
        _previous: QModelIndex,
    ) -> None:
        if not current.isValid() or self.event_df is None:
            return
        cid = self.case_model.case_id_at(current.row())
        if not cid:
            return
        row_idx_map = getattr(self, "_case_row_index", None) or None
        detail = get_case_detail(
            self.event_df,
            cid,
            case_row_index=row_idx_map,
        )
        self._display_case_detail(detail)
        self.case_selected.emit(cid)

    def _display_case_detail(
        self,
        detail: dict[str, Any],
        *,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        self._current_detail = detail
        cid = str(detail["case_id"])
        self._current_case_id = cid

        summary_info = self._summary_map.get(cid, {})
        variant_lbl = summary_info.get("variant_label", "")
        ev_count = int(detail.get("event_count", 0))

        self.lbl_case_title.setText(cid)
        sub_parts = [f"Case with {ev_count:,} events"]
        if variant_lbl:
            sub_parts.append(variant_lbl)
        if detail.get("first_activity") and detail.get("last_activity"):
            sub_parts.append(f"{detail['first_activity']} → {detail['last_activity']}")
        self.lbl_case_subtitle.setText("  ·  ".join(sub_parts))

        self.kpi_panel.set_value("events", f"{ev_count:,}")
        self.kpi_panel.set_value(
            "activities", f"{int(detail.get('unique_activities', 0)):,}"
        )
        start_raw = str(detail.get("start_time") or "—")
        self.kpi_panel.set_value("start", start_raw[:19].replace("T", " "))
        self.kpi_panel.set_value(
            "duration", str(detail.get("duration_human") or "—")
        )

        # Build smooth case event-progression profile for dark chart
        tl = detail.get("timeline", [])
        if len(tl) >= 2:
            # Plot inter-event intensity / cumulative progress profile
            profile_vals = [
                1.0 / (1.0 + math.log1p(max(0.0, float(e.get("delta_from_prev_seconds") or 0.0))))
                if i > 0
                else 1.0
                for i, e in enumerate(tl)
            ]
            self.case_chart.set_series(
                profile_vals,
                [f"Step 1", f"Step {len(tl)}"],
                kind="area",
                x_caption="Trace progression (higher = rapid consecutive activity)",
                y_caption="Pace",
            )
        elif len(tl) == 1:
            self.case_chart.set_series(
                [1.0],
                ["Step 1"],
                kind="bars",
                x_caption="Single-event trace",
            )
        else:
            self.case_chart.clear_chart()

        notes: list[str] = []
        if detail.get("has_invalid_timestamps"):
            notes.append(
                "This trace contains unparseable (NaT) timestamps; total duration is omitted."
            )
        missing_opt = []
        if not detail.get("has_lifecycle"):
            missing_opt.append("lifecycle:transition")
        if not detail.get("has_resource"):
            missing_opt.append("org:resource")
        if missing_opt:
            notes.append("Optional attributes absent in log: " + ", ".join(missing_opt) + ".")

        if notes:
            self.lbl_case_note.setText(" ".join(notes))
            self.lbl_case_note.show()
        else:
            self.lbl_case_note.hide()

        self.graph_widget.set_events(tl, highlight_activities=highlight_activities)
        self.timeline_model.set_timeline(
            tl,
            has_lifecycle=bool(detail.get("has_lifecycle")),
            has_resource=bool(detail.get("has_resource")),
            highlight_activities=highlight_activities,
        )
        self.btn_export_case.setEnabled(True)

        if tl:
            self._show_inspector_for_event(tl[0])
            if self.timeline_proxy.rowCount() > 0:
                self.timeline_table.selectRow(0)
        else:
            self.txt_event_inspector.clear()

    def _on_view_mode_changed(self, key: str) -> None:
        is_table = key == "table"
        self.trace_stack.setCurrentIndex(1 if is_table else 0)
        self.txt_activity_filter.setVisible(is_table)

    def _apply_activity_filter(self, text: str) -> None:
        self.timeline_proxy.setFilterFixedString(text.strip())

    def _on_graph_step_clicked(self, step_idx: int) -> None:
        ev = self.timeline_model.event_at(step_idx)
        if ev is not None:
            self._show_inspector_for_event(ev)

    def _on_table_event_selected(self) -> None:
        sel = self.timeline_table.selectionModel().selectedRows()
        if not sel:
            return
        src_row = self.timeline_proxy.mapToSource(sel[0]).row()
        ev = self.timeline_model.event_at(src_row)
        if ev is not None:
            self._show_inspector_for_event(ev)

    def _show_inspector_for_event(self, ev: dict[str, Any]) -> None:
        payload: dict[str, Any] = {
            "step": ev.get("step"),
            "case:concept:name": self._current_case_id,
            "concept:name": ev.get("activity"),
            "time:timestamp": ev.get("timestamp"),
            "delta_from_previous": ev.get("delta_from_prev_display"),
            "elapsed_from_start": ev.get("elapsed_from_start_display"),
        }
        if self._current_detail and self._current_detail.get("has_lifecycle"):
            payload["lifecycle:transition"] = ev.get("lifecycle")
        if self._current_detail and self._current_detail.get("has_resource"):
            payload["org:resource"] = ev.get("resource")
        for k, v in (ev.get("attributes") or {}).items():
            payload[str(k)] = v
        self.txt_event_inspector.setPlainText(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        )

    def _clear_all(self) -> None:
        self.variant_sidebar.set_header("Variants (0)")
        self.variant_sidebar.set_items([])
        self.lbl_cases_header.setText("Cases (0)")
        self.case_model.set_rows([])
        self.lbl_case_title.setText("No case selected")
        self.lbl_case_subtitle.setText("Select a case from the left list to inspect its trace")
        self.lbl_case_note.hide()
        self.kpi_panel.reset()
        self.case_chart.clear_chart()
        self.graph_widget.set_events([])
        self.timeline_model.set_timeline([], has_lifecycle=False, has_resource=False)
        self.txt_event_inspector.clear()
        self.btn_export_case.setEnabled(False)
        self.btn_export_list.setEnabled(False)


import math  # noqa: E402

__all__ = ["CaseExplorerPage"]
