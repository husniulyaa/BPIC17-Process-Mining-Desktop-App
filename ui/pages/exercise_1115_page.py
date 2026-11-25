"""Halaman GUI PySide6 untuk Exercise 11.15.

Menyediakan ``Exercise1115Page(QWidget)`` untuk menampilkan ringkasan hasil,
daftar case yang lolos, serta tabel bukti event untuk case yang dipilih.
Analisis dijalankan di background thread (``QThread``) agar UI tetap responsif.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable

import pandas as pd
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from analysis.exercise_1115 import EXERCISE_1115_RULE, analyze_exercise_1115


class AnalysisWorker(QObject):
    """Worker background untuk menjalankan fungsi analisis di luar UI thread."""

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
        """Menjalankan fungsi analisis dan memancarkan hasil atau pesan error."""
        try:
            result = self._analyzer_fn(self._event_df)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover - pengaman runtime GUI
            self.failed.emit(f"Terjadi kesalahan saat analisis: {exc}")


class BaseExercisePage(QWidget):
    """Komponen dasar QWidget untuk halaman hasil Exercise 11.15 dan 11.18.

    Signals:
        case_selected (str): Dipancarkan saat pengguna memilih baris case pada tabel
            untuk integrasi dengan Case Explorer.
        result_ready (dict): Dipancarkan setelah analisis selesai dijalankan dengan
            payload dict hasil analisis.
    """

    case_selected = Signal(str)
    result_ready = Signal(dict)

    def __init__(
        self,
        title: str,
        rule_description: str,
        analyzer_fn: Callable[[pd.DataFrame], dict[str, Any]],
        case_headers: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title_text = title
        self._rule_text = rule_description
        self._analyzer_fn = analyzer_fn
        self._case_headers = case_headers

        self._event_df: pd.DataFrame | None = None
        self._last_result: dict[str, Any] | None = None
        self._details: list[dict[str, Any]] = []
        self._thread: QThread | None = None
        self._worker: AnalysisWorker | None = None

        self._init_ui()
        self._reset_view()

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header judul & deskripsi aturan
        self.title_label = QLabel(self._title_text)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        root_layout.addWidget(self.title_label)

        self.rule_label = QLabel(self._rule_text)
        self.rule_label.setWordWrap(True)
        self.rule_label.setStyleSheet("color: #444444;")
        root_layout.addWidget(self.rule_label)

        # Baris kontrol tombol + status
        controls_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Analysis")
        self.reset_button = QPushButton("Reset")
        self.run_button.clicked.connect(self._on_run_clicked)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        controls_layout.addWidget(self.run_button)
        controls_layout.addWidget(self.reset_button)
        controls_layout.addSpacing(12)

        self.status_label = QLabel("Belum ada dataset")
        self.status_label.setWordWrap(True)
        controls_layout.addWidget(self.status_label, stretch=1)
        root_layout.addLayout(controls_layout)

        # Ringkasan angka
        summary_frame = QFrame()
        summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QHBoxLayout(summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)

        self.total_cases_label = QLabel("Case Lolos: -")
        self.total_cases_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.denominator_label = QLabel("Total Case di Log: -")
        self.denominator_label.setStyleSheet("font-size: 14px;")

        summary_layout.addWidget(self.total_cases_label)
        summary_layout.addSpacing(24)
        summary_layout.addWidget(self.denominator_label)
        summary_layout.addStretch()
        root_layout.addWidget(summary_frame)

        # Label peringatan jika ada warnings dari hasil analisis
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #9a6700;")
        self.warning_label.setVisible(False)
        root_layout.addWidget(self.warning_label)

        # Splitter tabel case (kiri) & tabel bukti event (kanan)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        case_container = QWidget()
        case_layout = QVBoxLayout(case_container)
        case_layout.setContentsMargins(0, 0, 0, 0)
        case_layout.addWidget(QLabel("Daftar Case Lolos"))

        self.case_table = QTableWidget(0, len(self._case_headers))
        self.case_table.setHorizontalHeaderLabels(self._case_headers)
        self.case_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.case_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.case_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.case_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.case_table.itemSelectionChanged.connect(self._on_case_row_selected)
        case_layout.addWidget(self.case_table)

        evidence_container = QWidget()
        evidence_layout = QVBoxLayout(evidence_container)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        evidence_layout.addWidget(QLabel("Bukti Event untuk Case Terpilih"))

        self.evidence_table = QTableWidget(0, 5)
        self.evidence_table.setHorizontalHeaderLabels(
            ["Timestamp", "Activity", "Lifecycle", "Resource", "EventID"]
        )
        self.evidence_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.evidence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        evidence_layout.addWidget(self.evidence_table)

        splitter.addWidget(case_container)
        splitter.addWidget(evidence_container)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        root_layout.addWidget(splitter, stretch=1)

    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        """Menyimpan referensi DataFrame event log dan mereset tampilan halaman."""
        self._event_df = event_df
        self._reset_view()

    def _reset_view(self) -> None:
        self._last_result = None
        self._details = []
        self.case_table.setRowCount(0)
        self.evidence_table.setRowCount(0)
        self.total_cases_label.setText("Case Lolos: -")
        self.denominator_label.setText("Total Case di Log: -")
        self.warning_label.clear()
        self.warning_label.setVisible(False)

        if self._event_df is None:
            self.status_label.setText("Belum ada dataset")
            self.run_button.setEnabled(False)
        else:
            self.status_label.setText(
                f"Dataset siap ({len(self._event_df):,} baris). Klik 'Run Analysis'."
            )
            self.run_button.setEnabled(self._thread is None)

    def _on_reset_clicked(self) -> None:
        self._reset_view()

    def _on_run_clicked(self) -> None:
        if self._event_df is None:
            self.status_label.setText("Belum ada dataset")
            return
        if self._thread is not None:
            return

        self.run_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.status_label.setText("Memproses...")

        self._thread = QThread(self)
        self._worker = AnalysisWorker(self._analyzer_fn, self._event_df)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_analysis_finished)
        self._worker.failed.connect(self._on_analysis_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)

        self._thread.start()

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None
        self.run_button.setEnabled(self._event_df is not None)
        self.reset_button.setEnabled(True)

    def _on_analysis_failed(self, error_message: str) -> None:
        self.status_label.setText(error_message)

    def _on_analysis_finished(self, result: dict[str, Any]) -> None:
        self._last_result = result
        self._details = list(result.get("details", []))

        total_cases = result.get("total_cases", 0)
        total_in_log = result.get("total_cases_in_log", 0)
        warnings = result.get("warnings", [])

        self.total_cases_label.setText(f"Case Lolos: {total_cases}")
        self.denominator_label.setText(f"Total Case di Log: {total_in_log}")

        if warnings:
            self.warning_label.setText("Peringatan: " + " | ".join(str(w) for w in warnings))
            self.warning_label.setVisible(True)
        else:
            self.warning_label.clear()
            self.warning_label.setVisible(False)

        self._populate_case_table(self._details)
        self.evidence_table.setRowCount(0)

        if self.case_table.rowCount() > 0:
            self.case_table.selectRow(0)

        self.status_label.setText(f"Selesai. Ditemukan {total_cases} case yang memenuhi aturan.")
        self.result_ready.emit(result)

    def _populate_case_table(self, details: list[dict[str, Any]]) -> None:
        """Mengisi tabel case sesuai struktur kolom masing-masing latihan."""
        raise NotImplementedError

    def _on_case_row_selected(self) -> None:
        selected_items = self.case_table.selectedItems()
        if not selected_items:
            return
        row_idx = selected_items[0].row()
        if row_idx < 0 or row_idx >= len(self._details):
            return

        detail = self._details[row_idx]
        case_id = str(detail.get("case_id", ""))
        self._populate_evidence_table(detail.get("evidence", []))
        self.case_selected.emit(case_id)

    def _populate_evidence_table(self, evidence: list[dict[str, Any]]) -> None:
        self.evidence_table.setRowCount(len(evidence))
        for row_idx, item in enumerate(evidence):
            values = [
                item.get("timestamp") or "-",
                item.get("activity") or "-",
                item.get("lifecycle") or "-",
                item.get("resource") or "-",
                str(item["EventID"]) if item.get("EventID") is not None else "-",
            ]
            for col_idx, val in enumerate(values):
                self.evidence_table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))


class Exercise1115Page(BaseExercisePage):
    """Halaman QWidget untuk menampilkan analisis Exercise 11.15."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Exercise 11.15",
            rule_description=EXERCISE_1115_RULE,
            analyzer_fn=analyze_exercise_1115,
            case_headers=["Case ID", "Complete Count"],
            parent=parent,
        )

    def _populate_case_table(self, details: list[dict[str, Any]]) -> None:
        self.case_table.setRowCount(len(details))
        for row_idx, item in enumerate(details):
            self.case_table.setItem(
                row_idx, 0, QTableWidgetItem(str(item.get("case_id", "")))
            )
            self.case_table.setItem(
                row_idx, 1, QTableWidgetItem(str(item.get("complete_count", 0)))
            )


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
            {
                "case:concept:name": "Demo_Case_02",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "schedule",
                "time:timestamp": "2016-01-02T09:00:00+00:00",
                "org:resource": "User_1",
                "EventID": "E_201",
            },
            {
                "case:concept:name": "Demo_Case_02",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-02T09:30:00+00:00",
                "org:resource": "User_1",
                "EventID": "E_202",
            },
        ]
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = Exercise1115Page()
    page.setWindowTitle("Demo Mandiri - Exercise 11.15")
    page.resize(960, 560)
    page.set_event_data(_build_demo_dataframe())
    page.show()
    sys.exit(app.exec())
