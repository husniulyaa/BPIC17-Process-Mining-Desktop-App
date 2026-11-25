"""Skrip runner lokal mandiri untuk melihat & menguji GUI Exercise 11.22 & Case Explorer.

Dijalankan secara lokal:
    python preview_app.py

Catatan: File ini hanya untuk preview/pengujian lokal sebelum MainWindow (Husni)
digabungkan, dan tidak perlu ikut di-commit ke branch PR jika tidak diperlukan.
"""

from __future__ import annotations

import gzip
import shutil
import sys
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.pages.case_explorer_page import CaseExplorerPage
from ui.pages.exercise_1122_page import Exercise1122Page


class _LoadXesWorker(QThread):
    """Worker background agar pembacaan file XES BPIC17 (~1,2 juta event) tidak freeze UI."""

    progress_text = Signal(str)
    completed = Signal(object, dict)
    failed = Signal(str)

    def __init__(self, file_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_path = Path(file_path)

    def run(self) -> None:
        try:
            target_path = self._file_path
            if target_path.name.lower().endswith(".xes.gz"):
                data_dir = Path(__file__).resolve().parent / "data"
                data_dir.mkdir(parents=True, exist_ok=True)
                extracted_name = target_path.name[:-3]  # hapus .gz -> .xes
                extracted_path = data_dir / extracted_name
                if not extracted_path.exists():
                    self.progress_text.emit(
                        f"Mengekstrak {target_path.name} ke data/{extracted_name}..."
                    )
                    with gzip.open(target_path, "rb") as src, extracted_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                target_path = extracted_path

            self.progress_text.emit(
                f"Membaca & memvalidasi {target_path.name} (file BPIC17 butuh ~20-60 detik)..."
            )
            from core.dataset_loader import load_xes

            df, meta = load_xes(target_path)
            self.completed.emit(df, dict(meta))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def create_demo_dataframe() -> pd.DataFrame:
    """Dataset sintetis representatif untuk menguji fitur 11.22 & Case Explorer."""
    return pd.DataFrame(
        [
            # Case 1: O_Cancelled diikuti O_Accepted (lolos 11.22)
            {
                "case:concept:name": "Application_001",
                "concept:name": "A_Create Application",
                "time:timestamp": "2026-01-01T08:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "LoanGoal": "Home improvement",
            },
            {
                "case:concept:name": "Application_001",
                "concept:name": "O_Created",
                "time:timestamp": "2026-01-01T08:30:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "OfferID": "Offer_1",
            },
            {
                "case:concept:name": "Application_001",
                "concept:name": "O_Cancelled",
                "time:timestamp": "2026-01-01T09:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "OfferID": "Offer_1",
            },
            {
                "case:concept:name": "Application_001",
                "concept:name": "W_Call after offers",
                "time:timestamp": "2026-01-01T11:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_2",
                "Action": "Contacted",
            },
            {
                "case:concept:name": "Application_001",
                "concept:name": "O_Created",
                "time:timestamp": "2026-01-02T09:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_2",
                "OfferID": "Offer_2",
            },
            {
                "case:concept:name": "Application_001",
                "concept:name": "O_Accepted",
                "time:timestamp": "2026-01-02T10:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_2",
                "OfferID": "Offer_2",
            },
            # Case 2: O_Accepted SEBELUM O_Cancelled (tidak lolos 11.22)
            {
                "case:concept:name": "Application_002",
                "concept:name": "A_Create Application",
                "time:timestamp": "2026-01-01T09:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_3",
                "LoanGoal": "Car",
            },
            {
                "case:concept:name": "Application_002",
                "concept:name": "O_Accepted",
                "time:timestamp": "2026-01-01T10:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_3",
                "OfferID": "Offer_3",
            },
            {
                "case:concept:name": "Application_002",
                "concept:name": "O_Cancelled",
                "time:timestamp": "2026-01-01T12:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_3",
                "OfferID": "Offer_3",
            },
            # Case 3: Hanya O_Cancelled (tidak lolos 11.22)
            {
                "case:concept:name": "Application_003",
                "concept:name": "A_Create Application",
                "time:timestamp": "2026-01-01T08:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_4",
                "LoanGoal": "Debt consolidation",
            },
            {
                "case:concept:name": "Application_003",
                "concept:name": "O_Cancelled",
                "time:timestamp": "2026-01-01T14:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_4",
                "OfferID": "Offer_4",
            },
            # Case 4: O_Cancelled lalu O_Accepted langsung (lolos 11.22)
            {
                "case:concept:name": "Application_004",
                "concept:name": "A_Create Application",
                "time:timestamp": "2026-01-02T08:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "LoanGoal": "Business",
            },
            {
                "case:concept:name": "Application_004",
                "concept:name": "O_Cancelled",
                "time:timestamp": "2026-01-02T09:30:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "OfferID": "Offer_5",
            },
            {
                "case:concept:name": "Application_004",
                "concept:name": "O_Accepted",
                "time:timestamp": "2026-01-02T11:00:00Z",
                "lifecycle:transition": "complete",
                "org:resource": "User_1",
                "OfferID": "Offer_5",
            },
        ]
    )


class PreviewWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Preview Bagian Farras — Exercise 11.22 & Case Explorer")
        self.resize(1150, 750)

        self._active_df: pd.DataFrame | None = None
        self._loader_worker: _LoadXesWorker | None = None

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Bar aksi atas
        top_bar = QHBoxLayout()
        self.btn_load_demo = QPushButton("Muat Data Demo (4 Kasus)")
        self.btn_load_demo.setStyleSheet("font-weight: bold; padding: 6px 12px;")
        self.btn_load_demo.clicked.connect(self._load_demo_data)

        self.btn_load_xes = QPushButton("Buka File .XES / .XES.GZ...")
        self.btn_load_xes.setStyleSheet("padding: 6px 12px;")
        self.btn_load_xes.clicked.connect(self._open_xes_file)

        self.lbl_loader_status = QLabel("Dataset aktif: Data Demo")
        self.loader_progress = QProgressBar()
        self.loader_progress.setRange(0, 0)
        self.loader_progress.setMaximumWidth(160)
        self.loader_progress.setTextVisible(False)
        self.loader_progress.hide()

        top_bar.addWidget(self.btn_load_demo)
        top_bar.addWidget(self.btn_load_xes)
        top_bar.addWidget(self.lbl_loader_status, 1)
        top_bar.addWidget(self.loader_progress)
        root.addLayout(top_bar)

        # Tabs antarmuka
        self.tabs = QTabWidget()
        self.p1122 = Exercise1122Page()
        self.explorer = CaseExplorerPage()

        self.tabs.addTab(self.p1122, "Exercise 11.22")
        self.tabs.addTab(self.explorer, "Case Explorer & Timeline")

        # Integrasi navigasi: klik tombol "Buka di Case Explorer" langsung lompat ke tab Explorer
        self.p1122.open_case_requested.connect(self._on_open_in_explorer)

        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        # Otomatis muat data demo di awal
        self._load_demo_data()

    def _on_open_in_explorer(self, case_id: str) -> None:
        self.tabs.setCurrentWidget(self.explorer)
        self.explorer.select_case(
            case_id,
            highlight_activities=["O_Cancelled", "O_Accepted"],
        )

    def _load_demo_data(self) -> None:
        df = create_demo_dataframe()
        self._active_df = df
        self.lbl_loader_status.setText("Dataset aktif: Data Demo (4 case, 14 event)")
        self.p1122.set_event_data(df)
        self.explorer.set_event_data(df)

    def _open_xes_file(self) -> None:
        if self._loader_worker is not None:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File XES atau XES.GZ",
            "",
            "XES Event Logs (*.xes *.xes.gz);;All Files (*)",
        )
        if not file_path:
            return

        self.btn_load_demo.setEnabled(False)
        self.btn_load_xes.setEnabled(False)
        self.loader_progress.show()
        self.lbl_loader_status.setText(f"Memuat {Path(file_path).name}...")

        worker = _LoadXesWorker(file_path, self)
        worker.progress_text.connect(self.lbl_loader_status.setText)
        worker.completed.connect(self._on_xes_loaded)
        worker.failed.connect(self._on_xes_failed)
        worker.finished.connect(self._on_xes_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self._loader_worker = worker
        worker.start()

    def _on_xes_loaded(self, df: pd.DataFrame, meta: dict) -> None:
        self._active_df = df
        self.lbl_loader_status.setText(
            f"Dataset aktif: {meta['file_name']} "
            f"({meta['case_count']:,} case, {meta['event_count']:,} event)"
        )
        self.p1122.set_event_data(df)
        self.explorer.set_event_data(df)

    def _on_xes_failed(self, message: str) -> None:
        self.lbl_loader_status.setText(f"Gagal memuat file: {message}")
        QMessageBox.critical(self, "Gagal Memuat XES", message)

    def _on_xes_worker_finished(self) -> None:
        self._loader_worker = None
        self.loader_progress.hide()
        self.btn_load_demo.setEnabled(True)
        self.btn_load_xes.setEnabled(True)


def main() -> None:
    app = QApplication(sys.argv)
    window = PreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
