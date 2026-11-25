"""Halaman GUI PySide6 Case Explorer, Timeline, dan Ekspor CSV (F07).

Memungkinkan pengguna menelusuri daftar case, memfilter berdasarkan Case ID
atau subset hasil latihan, melihat urutan event lengkap (timeline) beserta
delta waktu dan seluruh atribut event, serta mengekspor timeline atau daftar
case ke CSV.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

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
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from utils.case_timeline import (
    build_case_summaries,
    filter_case_summaries,
    get_case_detail,
)
from utils.exporter import (
    export_case_summaries_to_csv,
    export_case_timeline_to_csv,
    sanitize_filename_component,
)


class _CaseIndexWorker(QThread):
    """Worker background untuk membangun ringkasan seluruh case dari event_df."""

    completed = Signal(list)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            summaries = build_case_summaries(self._event_df)
            self.completed.emit(summaries)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class _CaseSummaryModel(QAbstractTableModel):
    """Model tabel virtual untuk daftar case di panel kiri Case Explorer."""

    HEADERS = ("Case ID", "Event", "Durasi", "Aktivitas Terakhir")

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

    def find_row(self, case_id: str) -> int:
        target = str(case_id)
        for idx, row in enumerate(self._rows):
            if str(row.get("case_id")) == target:
                return idx
        return -1

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

        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(row.get("case_id", ""))
            if col == 1:
                return str(row.get("event_count", 0))
            if col == 2:
                return str(row.get("duration_display", "—"))
            if col == 3:
                return str(row.get("last_activity", ""))

        if role == Qt.ItemDataRole.UserRole:
            if col == 0:
                return str(row.get("case_id", ""))
            if col == 1:
                return int(row.get("event_count") or 0)
            if col == 2:
                val = row.get("duration_seconds")
                return float(val) if val is not None else -1.0
            if col == 3:
                return str(row.get("last_activity", ""))

        if role == Qt.ItemDataRole.TextAlignmentRole and col in (1, 2):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None


class _TimelineTableModel(QAbstractTableModel):
    """Model tabel timeline event untuk satu case."""

    BASE_HEADERS = (
        "Step",
        "Timestamp (UTC)",
        "Aktivitas",
        "Δ Waktu",
        "Elapsed",
        "Lifecycle",
        "Resource",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: list[dict[str, Any]] = []
        self._has_lifecycle = False
        self._has_resource = False
        self._highlight_activities: set[str] = set()

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
        self._highlight_activities = {
            str(act).strip() for act in (highlight_activities or []) if str(act).strip()
        }
        self.endResetModel()

    def event_at(self, row_index: int) -> dict[str, Any] | None:
        if 0 <= row_index < len(self._events):
            return self._events[row_index]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.BASE_HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self.BASE_HEADERS)
        ):
            return self.BASE_HEADERS[section]
        return None

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid():
            return None

        event = self._events[index.row()]
        col = index.column()
        activity = str(event.get("activity", ""))

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(event.get("step", ""))
            if col == 1:
                return str(event.get("timestamp") or "NaT")
            if col == 2:
                return activity
            if col == 3:
                return str(event.get("delta_from_prev_display", "—"))
            if col == 4:
                return str(event.get("elapsed_from_start_display", "—"))
            if col == 5:
                if not self._has_lifecycle:
                    return "(tidak tersedia)"
                return str(event.get("lifecycle") or "—")
            if col == 6:
                if not self._has_resource:
                    return "(tidak tersedia)"
                return str(event.get("resource") or "—")

        if role == Qt.ItemDataRole.BackgroundRole:
            if activity in self._highlight_activities:
                return QBrush(QColor("#FFF3CD"))
            if activity == "O_Cancelled":
                return QBrush(QColor("#FDECEC"))
            if activity == "O_Accepted":
                return QBrush(QColor("#E8F7EE"))

        if role == Qt.ItemDataRole.TextAlignmentRole and col in (0, 3, 4):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None


class CaseExplorerPage(QWidget):
    """Halaman Case Explorer untuk menelusuri detail case, timeline, dan ekspor CSV."""

    case_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Case Explorer")

        self.event_df: pd.DataFrame | None = None
        self._all_summaries: list[dict[str, Any]] = []
        self._allowed_case_ids: set[str] | None = None
        self._filter_label: str = ""
        self._current_case_id: str | None = None
        self._current_detail: dict[str, Any] | None = None
        self._pending_case_id: str | None = None
        self._pending_highlights: list[str] | None = None
        self._worker: _CaseIndexWorker | None = None
        self._reindex_pending = False
        self._meta_labels: dict[str, QLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Case Explorer — Detail Case, Timeline & Ekspor CSV")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        # Toolbar atas
        toolbar = QHBoxLayout()
        self.txt_case_search = QLineEdit()
        self.txt_case_search.setPlaceholderText("Cari Case ID...")
        self.txt_case_search.setClearButtonEnabled(True)
        self.txt_case_search.textChanged.connect(self._refresh_case_list)

        self.btn_clear_filter = QPushButton("Tampilkan Semua Case")
        self.btn_clear_filter.clicked.connect(self.clear_case_filter)
        self.btn_clear_filter.hide()

        self.btn_export_case = QPushButton("Ekspor Timeline Case (CSV)")
        self.btn_export_case.clicked.connect(lambda: self.export_current_case_csv())
        self.btn_export_case.setEnabled(False)

        self.btn_export_list = QPushButton("Ekspor Daftar Case (CSV)")
        self.btn_export_list.clicked.connect(lambda: self.export_case_list_csv())
        self.btn_export_list.setEnabled(False)

        toolbar.addWidget(self.txt_case_search, 1)
        toolbar.addWidget(self.btn_clear_filter)
        toolbar.addWidget(self.btn_export_case)
        toolbar.addWidget(self.btn_export_list)
        root.addLayout(toolbar)

        # Baris status + loading indicator
        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Belum ada dataset aktif.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(160)
        self.progress.setTextVisible(False)
        self.progress.hide()
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.progress)
        root.addLayout(status_row)

        # Splitter utama (kiri: daftar case, kanan: timeline & atribut)
        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- Panel Kiri: Daftar Case ---
        left_panel = QWidget(main_splitter)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_case_count = QLabel("Daftar Case")
        self.lbl_case_count.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(self.lbl_case_count)

        self.case_model = _CaseSummaryModel(self)
        self.case_proxy = QSortFilterProxyModel(self)
        self.case_proxy.setSourceModel(self.case_model)
        self.case_proxy.setSortRole(Qt.ItemDataRole.UserRole)

        self.case_table = QTableView()
        self.case_table.setModel(self.case_proxy)
        self.case_table.setSortingEnabled(True)
        self.case_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.case_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.case_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.case_table.setAlternatingRowColors(True)
        self.case_table.verticalHeader().hide()
        self.case_table.horizontalHeader().setStretchLastSection(True)
        self.case_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.case_table.selectionModel().selectionChanged.connect(
            self._on_case_row_selected
        )
        left_layout.addWidget(self.case_table, 1)

        # --- Panel Kanan: Detail Case & Timeline ---
        right_panel = QWidget(main_splitter)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Kartu ringkasan case terpilih
        meta_grid = QGridLayout()
        meta_grid.setSpacing(8)
        meta_specs = (
            ("case_id", "Case ID"),
            ("event_count", "Total Event"),
            ("unique_activities", "Aktivitas Unik"),
            ("start_time", "Waktu Mulai (UTC)"),
            ("end_time", "Waktu Selesai (UTC)"),
            ("duration", "Cycle Time / Durasi"),
        )
        for idx, (key, caption) in enumerate(meta_specs):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet(
                "QFrame { border: 1px solid #c8c8c8; border-radius: 5px; }"
            )
            box = QVBoxLayout(frame)
            box.setContentsMargins(8, 6, 8, 6)
            lbl_cap = QLabel(caption)
            lbl_val = QLabel("—")
            lbl_val.setWordWrap(True)
            lbl_val.setStyleSheet("font-weight: bold;")
            box.addWidget(lbl_cap)
            box.addWidget(lbl_val)
            meta_grid.addWidget(frame, idx // 3, idx % 3)
            self._meta_labels[key] = lbl_val
        right_layout.addLayout(meta_grid)

        self.lbl_case_note = QLabel("")
        self.lbl_case_note.setWordWrap(True)
        self.lbl_case_note.setStyleSheet(
            "background-color: #FFF8E1; border: 1px solid #F0C36D; "
            "border-radius: 4px; padding: 6px; color: #5C4400;"
        )
        self.lbl_case_note.hide()
        right_layout.addWidget(self.lbl_case_note)

        # Filter aktivitas dalam timeline
        tl_header = QHBoxLayout()
        tl_title = QLabel("Timeline Event")
        tl_title.setStyleSheet("font-weight: bold;")
        self.txt_activity_filter = QLineEdit()
        self.txt_activity_filter.setPlaceholderText("Filter aktivitas dalam case...")
        self.txt_activity_filter.setClearButtonEnabled(True)
        self.txt_activity_filter.textChanged.connect(self._apply_activity_filter)
        tl_header.addWidget(tl_title)
        tl_header.addWidget(self.txt_activity_filter, 1)
        right_layout.addLayout(tl_header)

        right_splitter = QSplitter(Qt.Orientation.Vertical, right_panel)

        self.timeline_model = _TimelineTableModel(self)
        self.timeline_proxy = QSortFilterProxyModel(self)
        self.timeline_proxy.setSourceModel(self.timeline_model)
        self.timeline_proxy.setFilterKeyColumn(2)  # kolom Aktivitas
        self.timeline_proxy.setFilterCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )

        self.timeline_table = QTableView()
        self.timeline_table.setModel(self.timeline_proxy)
        self.timeline_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.timeline_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.timeline_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.timeline_table.setAlternatingRowColors(True)
        self.timeline_table.verticalHeader().hide()
        self.timeline_table.horizontalHeader().setStretchLastSection(True)
        self.timeline_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.timeline_table.selectionModel().selectionChanged.connect(
            self._on_event_row_selected
        )
        right_splitter.addWidget(self.timeline_table)

        # Inspector atribut event
        inspector_widget = QWidget(right_splitter)
        inspector_layout = QVBoxLayout(inspector_widget)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        lbl_inspector = QLabel("Detail Atribut Event Terpilih")
        lbl_inspector.setStyleSheet("font-weight: bold;")
        self.txt_event_inspector = QPlainTextEdit()
        self.txt_event_inspector.setReadOnly(True)
        self.txt_event_inspector.setPlaceholderText(
            "Pilih satu event pada timeline untuk melihat seluruh atribut sumber."
        )
        inspector_layout.addWidget(lbl_inspector)
        inspector_layout.addWidget(self.txt_event_inspector)
        right_splitter.addWidget(inspector_widget)

        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 1)
        right_layout.addWidget(right_splitter, 1)

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 4)
        root.addWidget(main_splitter, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        """Terima DataFrame event bersama dari Main Window dan indeks daftar case."""
        self.event_df = event_df
        self._all_summaries = []
        self._allowed_case_ids = None
        self._filter_label = ""
        self._current_case_id = None
        self._current_detail = None
        self.btn_clear_filter.hide()
        self._clear_all()

        if event_df is None or event_df.empty:
            self.lbl_status.setText("Dataset kosong atau belum dimuat.")
            self._reindex_pending = self._worker is not None
            return

        self._start_indexing()

    def select_case(
        self,
        case_id: str,
        highlight_activities: Sequence[str] | None = None,
    ) -> bool:
        """Pilih dan tampilkan detail satu case (mis. dipanggil dari halaman latihan)."""
        target = str(case_id).strip()
        if not target:
            return False

        if self._worker is not None:
            self._pending_case_id = target
            self._pending_highlights = (
                list(highlight_activities) if highlight_activities else None
            )
            return True

        if self.event_df is None or self.event_df.empty:
            self.lbl_status.setText("Dataset belum dimuat.")
            return False

        # Jika case sedang tersembunyi oleh filter subset, buka filter agar terlihat.
        if self._allowed_case_ids is not None and target not in self._allowed_case_ids:
            self.clear_case_filter()

        if self.txt_case_search.text().strip():
            self.txt_case_search.clear()

        detail = get_case_detail(self.event_df, target)
        if not detail.get("found"):
            self.lbl_status.setText(f"Case '{target}' tidak ditemukan pada dataset aktif.")
            return False

        self._display_case_detail(detail, highlight_activities=highlight_activities)

        source_row = self.case_model.find_row(target)
        if source_row >= 0:
            source_index = self.case_model.index(source_row, 0)
            proxy_index = self.case_proxy.mapFromSource(source_index)
            if proxy_index.isValid():
                self.case_table.selectionModel().blockSignals(True)
                try:
                    self.case_table.selectRow(proxy_index.row())
                    self.case_table.scrollTo(proxy_index)
                finally:
                    self.case_table.selectionModel().blockSignals(False)

        self.case_selected.emit(target)
        return True

    def set_case_filter(
        self,
        case_ids: Sequence[str] | None,
        label: str = "",
    ) -> None:
        """Batasi daftar case yang tampil pada subset tertentu (mis. hasil latihan)."""
        if case_ids is None:
            self.clear_case_filter()
            return
        self._allowed_case_ids = {str(cid) for cid in case_ids}
        self._filter_label = label.strip()
        self.btn_clear_filter.show()
        self._refresh_case_list()

    def clear_case_filter(self) -> None:
        """Hapus filter subset case agar seluruh case pada dataset tampil."""
        self._allowed_case_ids = None
        self._filter_label = ""
        self.btn_clear_filter.hide()
        self._refresh_case_list()

    def export_current_case_csv(
        self,
        file_path: str | Path | None = None,
    ) -> Path | None:
        """Ekspor timeline case yang sedang dipilih ke file CSV."""
        if self.event_df is None or not self._current_case_id:
            self.lbl_status.setText("Pilih satu case terlebih dahulu sebelum mengekspor.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            safe_id = sanitize_filename_component(self._current_case_id)
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Ekspor Timeline Case ke CSV",
                f"case_{safe_id}_timeline.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved_path = export_case_timeline_to_csv(
                self.event_df,
                self._current_case_id,
                target_path,
            )
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Gagal mengekspor timeline case: {exc}")
            QMessageBox.warning(
                self,
                "Ekspor Timeline Gagal",
                f"Tidak dapat mengekspor timeline case:\n{exc}",
            )
            return None

        self.lbl_status.setText(
            f"Timeline case '{self._current_case_id}' diekspor ke: {saved_path}"
        )
        return saved_path

    def export_case_list_csv(
        self,
        file_path: str | Path | None = None,
    ) -> Path | None:
        """Ekspor daftar ringkasan case yang sedang tampil ke file CSV."""
        visible_rows = self.case_model.rows()
        if not visible_rows:
            self.lbl_status.setText("Tidak ada daftar case untuk diekspor.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Ekspor Daftar Case ke CSV",
                "case_summaries.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved_path = export_case_summaries_to_csv(visible_rows, target_path)
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Gagal mengekspor daftar case: {exc}")
            QMessageBox.warning(
                self,
                "Ekspor Daftar Case Gagal",
                f"Tidak dapat mengekspor daftar case:\n{exc}",
            )
            return None

        self.lbl_status.setText(
            f"Daftar {len(visible_rows):,} case diekspor ke: {saved_path}"
        )
        return saved_path

    # ------------------------------------------------------------ internal
    def _start_indexing(self) -> None:
        if self.event_df is None or self.event_df.empty:
            return
        if self._worker is not None:
            self._reindex_pending = True
            return

        self.progress.show()
        self.lbl_status.setText("Memuat indeks daftar case...")
        worker = _CaseIndexWorker(self.event_df, self)
        worker.completed.connect(self._on_index_completed)
        worker.failed.connect(self._on_index_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_index_completed(self, summaries: list[dict[str, Any]]) -> None:
        if self._reindex_pending:
            return
        self._all_summaries = summaries
        self._refresh_case_list()
        self.lbl_status.setText(
            f"Siap. {len(summaries):,} case terindeks untuk ditelusuri."
        )

        if self._pending_case_id:
            cid = self._pending_case_id
            highlights = self._pending_highlights
            self._pending_case_id = None
            self._pending_highlights = None
            self.select_case(cid, highlight_activities=highlights)
        elif self.case_proxy.rowCount() > 0:
            self.case_table.selectRow(0)

    def _on_index_failed(self, message: str) -> None:
        if not self._reindex_pending:
            self.lbl_status.setText(f"Gagal memuat daftar case: {message}")

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.progress.hide()
        if self._reindex_pending:
            self._reindex_pending = False
            if self.event_df is not None and not self.event_df.empty:
                self._start_indexing()

    def _refresh_case_list(self) -> None:
        filtered = filter_case_summaries(
            self._all_summaries,
            query=self.txt_case_search.text(),
            allowed_case_ids=self._allowed_case_ids,
        )
        self.case_model.set_rows(filtered)
        self.btn_export_list.setEnabled(bool(filtered))

        total = len(self._all_summaries)
        shown = len(filtered)
        if self._filter_label:
            self.lbl_case_count.setText(
                f"Daftar Case ({self._filter_label}) — {shown:,} dari {total:,}"
            )
        else:
            self.lbl_case_count.setText(
                f"Daftar Case — menampilkan {shown:,} dari {total:,}"
            )

    def _on_case_row_selected(self) -> None:
        selection = self.case_table.selectionModel().selectedRows()
        if not selection or self.event_df is None:
            self._clear_case_detail()
            return

        source_row = self.case_proxy.mapToSource(selection[0]).row()
        case_id = self.case_model.case_id_at(source_row)
        if not case_id:
            self._clear_case_detail()
            return

        detail = get_case_detail(self.event_df, case_id)
        self._display_case_detail(detail)
        self.case_selected.emit(case_id)

    def _display_case_detail(
        self,
        detail: dict[str, Any],
        *,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        self._current_detail = detail
        self._current_case_id = str(detail["case_id"])

        self._meta_labels["case_id"].setText(self._current_case_id)
        self._meta_labels["event_count"].setText(f"{detail['event_count']:,}")
        self._meta_labels["unique_activities"].setText(
            f"{detail['unique_activities']:,}"
        )
        self._meta_labels["start_time"].setText(str(detail.get("start_time") or "—"))
        self._meta_labels["end_time"].setText(str(detail.get("end_time") or "—"))
        self._meta_labels["duration"].setText(str(detail.get("duration_display") or "—"))

        notes: list[str] = []
        if detail.get("has_invalid_timestamps"):
            notes.append(
                "Case ini memiliki timestamp tidak valid (NaT), sehingga durasi "
                "total tidak dapat dihitung secara pasti."
            )
        missing_optional = []
        if not detail.get("has_lifecycle"):
            missing_optional.append("lifecycle:transition")
        if not detail.get("has_resource"):
            missing_optional.append("org:resource")
        if missing_optional:
            notes.append(
                "Atribut opsional tidak tersedia pada dataset: "
                + ", ".join(missing_optional)
                + "."
            )

        if notes:
            self.lbl_case_note.setText(" ".join(notes))
            self.lbl_case_note.show()
        else:
            self.lbl_case_note.hide()

        self.timeline_model.set_timeline(
            detail.get("timeline", []),
            has_lifecycle=bool(detail.get("has_lifecycle")),
            has_resource=bool(detail.get("has_resource")),
            highlight_activities=highlight_activities,
        )
        self.btn_export_case.setEnabled(True)
        self.txt_event_inspector.clear()

        if self.timeline_proxy.rowCount() > 0:
            self.timeline_table.selectRow(0)

    def _apply_activity_filter(self, text: str) -> None:
        self.timeline_proxy.setFilterFixedString(text.strip())

    def _on_event_row_selected(self) -> None:
        selection = self.timeline_table.selectionModel().selectedRows()
        if not selection:
            self.txt_event_inspector.clear()
            return

        source_row = self.timeline_proxy.mapToSource(selection[0]).row()
        event = self.timeline_model.event_at(source_row)
        if event is None:
            self.txt_event_inspector.clear()
            return

        payload: dict[str, Any] = {
            "step": event.get("step"),
            "case:concept:name": self._current_case_id,
            "concept:name": event.get("activity"),
            "time:timestamp": event.get("timestamp"),
            "delta_from_prev": event.get("delta_from_prev_display"),
            "elapsed_from_start": event.get("elapsed_from_start_display"),
        }
        if self._current_detail and self._current_detail.get("has_lifecycle"):
            payload["lifecycle:transition"] = event.get("lifecycle")
        if self._current_detail and self._current_detail.get("has_resource"):
            payload["org:resource"] = event.get("resource")
        for attr_key, attr_val in (event.get("attributes") or {}).items():
            payload[str(attr_key)] = attr_val

        self.txt_event_inspector.setPlainText(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        )

    def _clear_case_detail(self) -> None:
        self._current_case_id = None
        self._current_detail = None
        for label in self._meta_labels.values():
            label.setText("—")
        self.lbl_case_note.hide()
        self.timeline_model.set_timeline([], has_lifecycle=False, has_resource=False)
        self.txt_event_inspector.clear()
        self.btn_export_case.setEnabled(False)

    def _clear_all(self) -> None:
        self.case_model.set_rows([])
        self.lbl_case_count.setText("Daftar Case")
        self.btn_export_list.setEnabled(False)
        self._clear_case_detail()


__all__ = ["CaseExplorerPage"]
