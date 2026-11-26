"""Entry point for Disco - Lite (by Kelompok 7) Process Mining Desktop App."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, QSS


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    window = MainWindow()
    window.dataset_requested.connect(window.load_data_file)

    if "--demo" in sys.argv:
        window._load_sample_log()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
