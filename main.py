
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread, Signal

from ui.main_window import MainWindow, QSS
from core.dataset_loader import load_xes


class XESLoaderWorker(QThread):
    loaded = Signal(object, object, str)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            event_df, metadata = load_xes(self.path)
            self.loaded.emit(event_df, metadata, self.path)
        except Exception as error:
            self.failed.emit(str(error))


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    window = MainWindow()

    def start_loading(path):
        if hasattr(window, "_loader_worker"):
            if window._loader_worker.isRunning():
                return

        window._set_status("Loading dataset…", "busy")

        window._loader_worker = XESLoaderWorker(path)

        def on_loaded(df, metadata, loaded_path):
            window.set_event_data(df, path=loaded_path)
            window._set_status(
                f"Dataset loaded · {metadata['event_count']:,} events",
                "ok"
            )

        def on_failed(message):
            window.show_error(f"Load failed: {message}")

        window._loader_worker.loaded.connect(on_loaded)
        window._loader_worker.failed.connect(on_failed)
        window._loader_worker.start()

    window.dataset_requested.connect(start_loading)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
