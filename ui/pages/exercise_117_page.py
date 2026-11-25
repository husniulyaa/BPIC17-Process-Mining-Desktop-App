from __future__ import annotations

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
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from analysis.exercise_117 import SUBQUESTIONS, analyze_exercise_117

CARD_LABELS = {
    "11.7 A": "Total Cases",
    "11.7 B": "Mean Cycle Time (All)",
    "11.7 C": "Successful (O_Accepted)",
    "11.7 D": "Unsuccessful (O_Refused)",
    "11.7 E": "Canceled (Last O_Cancelled)",
}


class _Analyze117Worker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, event_df: pd.DataFrame, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_df = event_df

    def run(self) -> None:
        try:
            self.completed.emit(analyze_exercise_117(self._event_df))
        except Exception as exc:  # noqa: BLE001 - ditampilkan ke pengguna
            self.failed.emit(str(exc))


def _detail_by_code(result: dict[str, Any] | None, code: str) -> dict[str, Any]:
    """Ambil elemen ``details`` (list) untuk satu subsoal, mis. "11.7 C"."""
    for item in (result or {}).get("details", []):
        if item.get("code") == code:
            return item
    return {}


def _evidence_text(row: dict[str, Any]) -> str:
    events = row.get("evidence_events") or []
    if not events:
        return (
            f"{row.get('n_events', '?')} event | "
            f"{row.get('first_timestamp', '-')} -> {row.get('last_timestamp', '-')}"
        )
    shown = ", ".join(f"{e['activity']} @pos {e['index']} ({e['timestamp']})" for e in events[:2])
    if len(events) > 2:
        shown += f" (+{len(events) - 2} event lain)"
    return shown


class _CaseTableModel(QAbstractTableModel):
    """Model ringan: baris dibuat saat ditampilkan, aman untuk puluhan ribu case."""

    HEADERS = ["Case ID", "Cycle Time (hari)", "Event Cocok", "Bukti"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def case_id_at(self, row: int) -> str:
        return str(self._rows[row]["case_id"])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return str(row["case_id"])
            if col == 1:
                return f"{float(row['cycle_time_days']):.2f}"
            if col == 2:
                return str(row.get("matched_count", 1))
            return _evidence_text(row)
        if role == Qt.UserRole:  # nilai untuk sorting (numerik untuk kolom angka)
            if col == 0:
                return str(row["case_id"])
            if col == 1:
                return float(row["cycle_time_days"])
            if col == 2:
                return int(row.get("matched_count", 1))
            return _evidence_text(row)
        if role == Qt.TextAlignmentRole and col in (1, 2):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None


class Exercise117Page(QWidget):
    """Menampilkan ringkasan, aturan filter, dan daftar case Exercise 11.7 A-E."""

    open_case_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.event_df: pd.DataFrame | None = None
        self._result: dict[str, Any] | None = None
        self._worker: _Analyze117Worker | None = None
        self._rerun_pending = False
        self._cards: dict[str, dict[str, QLabel]] = {}
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Exercise 11.7 (A-E) - Jumlah Case & Mean Cycle Time")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.btn_run = QPushButton("Jalankan / Hitung Ulang")
        self.btn_run.clicked.connect(self.run_analysis)
        self.btn_reset = QPushButton("Reset Tampilan")
        self.btn_reset.clicked.connect(self._reset_view)
        self.combo_subsoal = QComboBox()
        self.combo_subsoal.addItems(list(SUBQUESTIONS))
        self.combo_subsoal.currentTextChanged.connect(self._show_subquestion)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Cari Case ID...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._apply_search)
        self.btn_detail = QPushButton("Buka Detail Case")
        self.btn_detail.clicked.connect(self._on_open_case_clicked)

        controls.addWidget(self.btn_run)
        controls.addWidget(self.btn_reset)
        controls.addWidget(QLabel("Subsoal:"))
        controls.addWidget(self.combo_subsoal)
        controls.addWidget(self.txt_search, 1)
        controls.addWidget(self.btn_detail)
        layout.addLayout(controls)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Belum ada dataset aktif.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.setMaximumWidth(160)
        self.progress.setTextVisible(False)
        self.progress.hide()
        status_row.addWidget(self.lbl_status, 1)
        status_row.addWidget(self.progress)
        layout.addLayout(status_row)

        cards = QGridLayout()
        cards.setSpacing(10)
        for idx, code in enumerate(SUBQUESTIONS):
            frame = QFrame()
            frame.setFrameShape(QFrame.StyledPanel)
            box = QVBoxLayout(frame)
            lbl_title = QLabel(f"{code} - {CARD_LABELS[code]}")
            lbl_title.setStyleSheet("font-weight: bold;")
            lbl_count = QLabel("Jumlah Case: -")
            lbl_mean = QLabel("Mean Cycle Time: -")
            box.addWidget(lbl_title)
            box.addWidget(lbl_count)
            box.addWidget(lbl_mean)
            self._cards[code] = {"count": lbl_count, "mean": lbl_mean}
            cards.addWidget(frame, idx // 3, idx % 3)
        layout.addLayout(cards)

        self.lbl_rule = QLabel("Aturan Filter: -")
        self.lbl_rule.setWordWrap(True)
        layout.addWidget(self.lbl_rule)

        self.lbl_count = QLabel("")
        layout.addWidget(self.lbl_count)

        self.model = _CaseTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.UserRole)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.doubleClicked.connect(lambda _idx: self._on_open_case_clicked())
        layout.addWidget(self.table, 1)

    # ----------------------------------------------------------- data API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        """Dipanggil Main Window saat dataset aktif berubah."""
        self.event_df = event_df
        self._result = None
        self._clear_view()
        if event_df is None or event_df.empty:
            self.lbl_status.setText("Dataset kosong atau belum dimuat.")
            # Jika worker lama masih jalan, hasilnya harus dibuang.
            self._rerun_pending = self._worker is not None
            return
        self.run_analysis()

    def run_analysis(self) -> None:
        if self.event_df is None or self.event_df.empty:
            self.lbl_status.setText("Tidak ada dataset untuk diproses.")
            return
        if self._worker is not None:
            # Worker lama masih jalan: hasilnya basi, ulangi setelah selesai.
            self._rerun_pending = True
            return

        self.btn_run.setEnabled(False)
        self.progress.show()
        self.lbl_status.setText("Memproses Exercise 11.7 (A-E)...")

        worker = _Analyze117Worker(self.event_df, self)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    # ------------------------------------------------------------ slots
    def _on_completed(self, result: dict[str, Any]) -> None:
        if self._rerun_pending:  # dataset berganti saat menghitung
            return
        self._result = result
        for code, widgets in self._cards.items():
            sub = _detail_by_code(result, code)
            widgets["count"].setText(f"Jumlah Case: {sub.get('total_cases', 0):,}")
            widgets["mean"].setText(f"Mean Cycle Time: {sub.get('mean_cycle_time_days', 0.0):.2f} hari")
        self.lbl_status.setText(
            f"Selesai. Denominator (total case aktif): {result.get('total_cases', 0):,} | "
            f"Mean cycle time semua case: {result.get('mean_cycle_time_days', 0.0):.2f} hari"
        )
        self._show_subquestion(self.combo_subsoal.currentText())

    def _on_failed(self, message: str) -> None:
        if not self._rerun_pending:
            self.lbl_status.setText(f"Error saat menjalankan Exercise 11.7: {message}")

    def _on_worker_finished(self) -> None:
        self._worker = None
        self.progress.hide()
        self.btn_run.setEnabled(True)
        if self._rerun_pending:
            self._rerun_pending = False
            self.run_analysis()

    def _show_subquestion(self, code: str) -> None:
        if not self._result:
            self.model.set_rows([])
            self._update_count()
            return
        sub = _detail_by_code(self._result, code)
        self.lbl_rule.setText(f"Aturan Filter ({code}): {sub.get('rule', '-')}")
        self.model.set_rows(sub.get("case_evidence", []))
        self._update_count()

    def _apply_search(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())
        self._update_count()

    def _update_count(self) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        self.lbl_count.setText(f"Menampilkan {shown:,} dari {total:,} case" if total else "")

    def _reset_view(self) -> None:
        self.txt_search.clear()
        self.combo_subsoal.setCurrentIndex(0)
        self.table.sortByColumn(-1, Qt.AscendingOrder)
        self._show_subquestion(self.combo_subsoal.currentText())

    def _clear_view(self) -> None:
        for widgets in self._cards.values():
            widgets["count"].setText("Jumlah Case: -")
            widgets["mean"].setText("Mean Cycle Time: -")
        self.lbl_rule.setText("Aturan Filter: -")
        self.model.set_rows([])
        self._update_count()

    def _on_open_case_clicked(self) -> None:
        selection = self.table.selectionModel().selectedRows()
        if not selection:
            self.lbl_status.setText("Pilih satu baris Case ID pada tabel terlebih dahulu.")
            return
        source_row = self.proxy.mapToSource(selection[0]).row()
        self.open_case_requested.emit(self.model.case_id_at(source_row))