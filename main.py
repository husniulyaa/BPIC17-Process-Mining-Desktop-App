
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow, QSS


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    window = MainWindow()

    # Temporary XES loader menggunakan PM4Py.
    # Nanti bisa diganti dengan integrasi loader dari Nabila.
    def load_xes(path):
        try:
            import pm4py

            QApplication.setOverrideCursor(Qt.WaitCursor)

            event_df = pm4py.read_xes(path)

            window.set_event_data(
                event_df,
                path=path
            )

        except ImportError:
            window.show_error(
                "PM4Py belum terpasang. Jalankan pip install pm4py"
            )

        except Exception as error:
            window.show_error(
                f"Load failed: {error}"
            )

        finally:
            while QApplication.overrideCursor():
                QApplication.restoreOverrideCursor()

    window.dataset_requested.connect(load_xes)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
