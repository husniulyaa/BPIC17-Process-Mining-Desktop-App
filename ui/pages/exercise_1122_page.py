"""Halaman GUI PySide6 untuk Exercise 11.22 (F06).

Menampilkan ringkasan hasil analisis ``analysis.exercise_1122``, daftar case
yang memiliki ``O_Cancelled`` diikuti ``O_Accepted`` pada waktu lebih akhir,
cuplikan timeline/evidence per case, navigasi ke Case Explorer, dan ekspor CSV.
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
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from analysis.exercise_1122 import (
    ACCEPTED_ACTIVITY,
    CANCELLED_ACTIVITY,
    EXERCISE_1122_RULE,
    LIFECYCLE_ATTRIBUTE,
    RESOURCE_ATTRIBUTE,
    analyze_exercise_1122,
)
from utils.exporter import export_analysis_result_to_csv


class _Analyze1122Worker(QThread):
    """Worker background untuk menjalankan analisis Exercise 11.22 di luar UI thread."""

    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            result = analyze_exercise_1122(self._event_df)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - tampilkan pesan ramah ke pengguna
            self.failed.emit(str(exc))


class _Exercise1122CaseModel(QAbstractTableModel):
    """Model tabel ringan untuk daftar case hasil Exercise 11.22."""

    HEADERS = (
        "Case ID",
        "O_Cancelled Pertama",
        "O_Accepted Setelahnya",
        "Selisih Waktu",
        "Event Antara",
        "Total Event",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

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
                return str(row.get("first_cancelled_timestamp") or "—")
            if col == 2:
                return str(row.get("first_accepted_after_cancelled_timestamp") or "—")
            if col == 3:
                return str(row.get("time_between_display") or "—")
            if col == 4:
                return str(row.get("events_between_count", 0))
            if col == 5:
                return str(row.get("total_events", 0))

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

        if role == Qt.ItemDataRole.TextAlignmentRole and col in (3, 4, 5):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None


class _EvidenceTimelineModel(QAbstractTableModel):
    """Model tabel cuplikan timeline/evidence untuk case terpilih."""

    HEADERS = (
        "Step",
        "Aktivitas",
        "Timestamp (UTC)",
        "Lifecycle",
        "Resource",
        "Peran Evidence",
    )

    _ROLE_LABELS = {
        "first_o_cancelled": "O_Cancelled pertama",
        "first_o_accepted_after_cancelled": "O_Accepted setelah O_Cancelled",
        "o_accepted_after_cancelled": "O_Accepted lanjutan",
        "o_accepted_not_after_cancelled": "O_Accepted sebelum/sama waktu",
        "o_cancelled": "O_Cancelled lain",
        "intermediate": "Event perantara",
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

        event = self._events[index.row()]
        col = index.column()
        activity = str(event.get("activity", ""))

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(event.get("step", ""))
            if col == 1:
                return activity
            if col == 2:
                return str(event.get("timestamp") or "NaT")
            if col == 3:
                if LIFECYCLE_ATTRIBUTE not in event:
                    return "(tidak tersedia)"
                return str(event.get(LIFECYCLE_ATTRIBUTE) or "—")
            if col == 4:
                if RESOURCE_ATTRIBUTE not in event:
                    return "(tidak tersedia)"
                return str(event.get(RESOURCE_ATTRIBUTE) or "—")
            if col == 5:
                raw_role = str(event.get("role", ""))
                return self._ROLE_LABELS.get(raw_role, raw_role or "—")

        if role == Qt.ItemDataRole.BackgroundRole:
            if activity == CANCELLED_ACTIVITY:
                return QBrush(QColor("#FDECEC"))
            if activity == ACCEPTED_ACTIVITY:
                return QBrush(QColor("#E8F7EE"))

        if role == Qt.ItemDataRole.TextAlignmentRole and col == 0:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        return None


class Exercise1122Page(QWidget):
    """Halaman hasil Exercise 11.22 (``O_Cancelled`` diikuti ``O_Accepted``).

    Signals:
        open_case_requested (str): Dipancarkan saat pengguna membuka case di
            Case Explorer (selaras dengan ``Exercise117Page``).
        case_selected (str): Alias sinyal pilihan case untuk integrasi lintas
            halaman (selaras dengan ``Exercise1115Page``).
        result_ready (dict): Dipancarkan saat analisis selesai dengan payload
            dict hasil ``analyze_exercise_1122``.
    """

    open_case_requested = Signal(str)
    case_selected = Signal(str)
    result_ready = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exercise 11.22")

        self.event_df: pd.DataFrame | None = None
        self._result: dict[str, Any] | None = None
        self._worker: _Analyze1122Worker | None = None
        self._rerun_pending = False
        self._metric_labels: dict[str, QLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Exercise 11.22 — O_Cancelled Diikuti O_Accepted")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        self.lbl_rule = QLabel(f"Aturan: {EXERCISE_1122_RULE}")
        self.lbl_rule.setWordWrap(True)
        self.lbl_rule.setStyleSheet("color: #444444;")
        root.addWidget(self.lbl_rule)

        # Baris kontrol
        controls = QHBoxLayout()
        self.btn_run = QPushButton("Jalankan / Hitung Ulang")
        self.btn_run.clicked.connect(self.run_analysis)

        self.btn_reset = QPushButton("Reset Tampilan")
        self.btn_reset.clicked.connect(self._reset_view)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Cari Case ID...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._apply_search)

        self.btn_open_explorer = QPushButton("Buka di Case Explorer")
        self.btn_open_explorer.clicked.connect(self._on_open_case_clicked)
        self.btn_open_explorer.setEnabled(False)

        self.btn_export = QPushButton("Ekspor CSV")
        self.btn_export.clicked.connect(lambda: self.export_results())
        self.btn_export.setEnabled(False)

        controls.addWidget(self.btn_run)
        controls.addWidget(self.btn_reset)
        controls.addWidget(self.txt_search, 1)
        controls.addWidget(self.btn_open_explorer)
        controls.addWidget(self.btn_export)
        root.addLayout(controls)

        # Status & loading bar
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

        # Kartu ringkasan metrik
        cards_layout = QGridLayout()
        cards_layout.setSpacing(10)
        metric_specs = (
            ("matched", "Case Memenuhi 11.22"),
            ("total_log", "Total Case di Log"),
            ("percentage", "Persentase Case"),
            ("same_ts", "Timestamp Sama (Dikecualikan)"),
        )
        for col_idx, (key, caption) in enumerate(metric_specs):
            frame = QFrame()
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setStyleSheet(
                "QFrame { border: 1px solid #c8c8c8; border-radius: 5px; }"
            )
            box = QVBoxLayout(frame)
            box.setContentsMargins(10, 8, 10, 8)
            lbl_cap = QLabel(caption)
            lbl_val = QLabel("—")
            lbl_val.setStyleSheet("font-size: 16px; font-weight: bold;")
            box.addWidget(lbl_cap)
            box.addWidget(lbl_val)
            cards_layout.addWidget(frame, 0, col_idx)
            self._metric_labels[key] = lbl_val
        root.addLayout(cards_layout)

        # Banner peringatan (tampil hanya jika ada warnings)
        self.lbl_warnings = QLabel("")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet(
            "background-color: #FFF8E1; border: 1px solid #F0C36D; "
            "border-radius: 4px; padding: 6px; color: #5C4400;"
        )
        self.lbl_warnings.hide()
        root.addWidget(self.lbl_warnings)

        # Splitter daftar case dan panel evidence
        splitter = QSplitter(Qt.Orientation.Vertical, self)

        # Panel atas: tabel case cocok
        top_panel = QWidget(splitter)
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_count = QLabel("")
        top_layout.addWidget(self.lbl_count)

        self.case_model = _Exercise1122CaseModel(self)
        self.case_proxy = QSortFilterProxyModel(self)
        self.case_proxy.setSourceModel(self.case_model)
        self.case_proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.case_proxy.setFilterKeyColumn(0)
        self.case_proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

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
            self._on_case_selection_changed
        )
        self.case_table.doubleClicked.connect(
            lambda _idx: self._on_open_case_clicked()
        )
        top_layout.addWidget(self.case_table, 1)

        # Panel bawah: evidence / cuplikan timeline
        bottom_panel = QWidget(splitter)
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_evidence_title = QLabel(
            "Cuplikan Timeline & Evidence (pilih satu case pada tabel di atas)"
        )
        self.lbl_evidence_title.setStyleSheet("font-weight: bold;")
        bottom_layout.addWidget(self.lbl_evidence_title)

        self.evidence_model = _EvidenceTimelineModel(self)
        self.evidence_table = QTableView()
        self.evidence_table.setModel(self.evidence_model)
        self.evidence_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.evidence_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.evidence_table.setAlternatingRowColors(True)
        self.evidence_table.verticalHeader().hide()
        self.evidence_table.horizontalHeader().setStretchLastSection(True)
        self.evidence_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        bottom_layout.addWidget(self.evidence_table, 1)

        splitter.addWidget(top_panel)
        splitter.addWidget(bottom_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        """Terima DataFrame event bersama dari Main Window dan jalankan analisis."""
        self.event_df = event_df
        self._result = None
        self._clear_view()

        if event_df is None or event_df.empty:
            self.lbl_status.setText("Dataset kosong atau belum dimuat.")
            self._rerun_pending = self._worker is not None
            return

        self.run_analysis()

    def run_analysis(self) -> None:
        """Jalankan analisis Exercise 11.22 secara asinkron di QThread."""
        if self.event_df is None or self.event_df.empty:
            self.lbl_status.setText("Tidak ada dataset aktif untuk dianalisis.")
            return

        if self._worker is not None:
            self._rerun_pending = True
            return

        self.btn_run.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Menjalankan analisis Exercise 11.22...")

        worker = _Analyze1122Worker(self.event_df, self)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def get_result(self) -> dict[str, Any] | None:
        """Kembalikan hasil analisis terakhir (atau ``None`` jika belum ada)."""
        return self._result

    def export_results(self, file_path: str | Path | None = None) -> Path | None:
        """Ekspor hasil analisis Exercise 11.22 ke file CSV."""
        if self._result is None:
            self.lbl_status.setText("Belum ada hasil analisis untuk diekspor.")
            return None

        target_path: str | Path | None = file_path
        if target_path is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Ekspor Hasil Exercise 11.22 ke CSV",
                "exercise_1122_results.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target_path = selected

        try:
            saved_path = export_analysis_result_to_csv(self._result, target_path)
        except Exception as exc:  # noqa: BLE001
            self.lbl_status.setText(f"Gagal mengekspor CSV: {exc}")
            QMessageBox.warning(
                self,
                "Ekspor CSV Gagal",
                f"Tidak dapat menyimpan hasil ke CSV:\n{exc}",
            )
            return None

        self.lbl_status.setText(f"Hasil Exercise 11.22 diekspor ke: {saved_path}")
        return saved_path

    # ------------------------------------------------------------ slots
    def _on_completed(self, result: dict[str, Any]) -> None:
        if self._rerun_pending:
            return

        self._result = result
        matched = int(result.get("total_cases", 0))
        total_log = int(result.get("total_cases_in_log", 0))
        pct = (matched / total_log * 100.0) if total_log > 0 else 0.0
        same_ts_count = len(result.get("same_timestamp_cases", []))

        self._metric_labels["matched"].setText(f"{matched:,}")
        self._metric_labels["total_log"].setText(f"{total_log:,}")
        self._metric_labels["percentage"].setText(f"{pct:.2f}%")
        self._metric_labels["same_ts"].setText(f"{same_ts_count:,}")

        warnings = result.get("warnings") or []
        if warnings:
            self.lbl_warnings.setText(
                "Catatan / Peringatan:\n• " + "\n• ".join(warnings)
            )
            self.lbl_warnings.show()
        else:
            self.lbl_warnings.hide()

        self.case_model.set_rows(result.get("details", []))
        self.evidence_model.set_events([])
        self.btn_export.setEnabled(True)
        self._update_count()

        if matched == 0:
            self.lbl_status.setText(
                f"Selesai. Tidak ditemukan case dengan O_Cancelled diikuti "
                f"O_Accepted (dari {total_log:,} case)."
            )
        else:
            self.lbl_status.setText(
                f"Selesai. Ditemukan {matched:,} case dari {total_log:,} total case "
                f"({pct:.2f}%)."
            )
            self.case_table.selectRow(0)

        self.result_ready.emit(result)

    def _on_failed(self, message: str) -> None:
        if not self._rerun_pending:
            self.lbl_status.setText(f"Error saat menjalankan Exercise 11.22: {message}")

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
            self.lbl_evidence_title.setText(
                "Cuplikan Timeline & Evidence (pilih satu case pada tabel di atas)"
            )
            return

        self.btn_open_explorer.setEnabled(True)
        case_id = str(row_data.get("case_id", ""))
        excerpt = row_data.get("timeline_excerpt") or row_data.get("evidence_events") or []
        between = int(row_data.get("events_between_count", 0))
        delta = str(row_data.get("time_between_display", "—"))
        self.lbl_evidence_title.setText(
            f"Cuplikan Timeline Case '{case_id}' — {len(excerpt)} event "
            f"({between} event antara O_Cancelled & O_Accepted, selisih {delta})"
        )
        self.evidence_model.set_events(excerpt)

    def _selected_case_row(self) -> dict[str, Any] | None:
        selection = self.case_table.selectionModel().selectedRows()
        if not selection:
            return None
        source_index = self.case_proxy.mapToSource(selection[0])
        return self.case_model.row_at(source_index.row())

    def _on_open_case_clicked(self) -> None:
        row_data = self._selected_case_row()
        if row_data is None:
            self.lbl_status.setText("Pilih satu baris Case ID terlebih dahulu.")
            return
        case_id = str(row_data["case_id"])
        self.open_case_requested.emit(case_id)
        self.case_selected.emit(case_id)

    def _apply_search(self, text: str) -> None:
        self.case_proxy.setFilterFixedString(text.strip())
        self._update_count()

    def _update_count(self) -> None:
        total = self.case_model.rowCount()
        shown = self.case_proxy.rowCount()
        self.lbl_count.setText(
            f"Menampilkan {shown:,} dari {total:,} case yang cocok" if total else ""
        )

    def _reset_view(self) -> None:
        self.txt_search.clear()
        self.case_table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self._update_count()

    def _clear_view(self) -> None:
        for label in self._metric_labels.values():
            label.setText("—")
        self.lbl_warnings.hide()
        self.case_model.set_rows([])
        self.evidence_model.set_events([])
        self.lbl_evidence_title.setText(
            "Cuplikan Timeline & Evidence (pilih satu case pada tabel di atas)"
        )
        self.btn_open_explorer.setEnabled(False)
        self.btn_export.setEnabled(False)
        self._update_count()


__all__ = ["Exercise1122Page"]
