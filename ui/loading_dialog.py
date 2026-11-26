"""Modal Fluxicon Disco-styled Loading Pop-up Dialog."""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QConicalGradient, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class _DiscoSpinnerWidget(QWidget):
    """Smooth rotating steel-blue arc spinner inside the loading modal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(44, 44)
        self._angle = 0

    def advance(self) -> None:
        self._angle = (self._angle - 18) % 360
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(5.0, 5.0, 34.0, 34.0)

        # Subtle background track ring
        painter.setPen(QPen(QColor("#DCE4EE"), 4.0))
        painter.drawEllipse(rect)

        # Spinning active steel-blue arc
        grad = QConicalGradient(rect.center(), float(self._angle))
        grad.setColorAt(0.0, QColor("#1F5C99"))
        grad.setColorAt(0.65, QColor("#5AA4EC"))
        grad.setColorAt(1.0, QColor(90, 164, 236, 0))
        pen = QPen()
        pen.setWidthF(4.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setBrush(grad)
        painter.setPen(pen)
        painter.drawArc(rect, self._angle * 16, 250 * 16)


class DiscoLoadingDialog(QDialog):
    """Centered modal pop-up dialog shown during file import and column mapping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint,
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowTitle("Disco - Lite · Processing")
        self.setFixedSize(430, 178)

        self._start_ts = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background: #F7F9FC;
            }
            QFrame#modalBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #3D6E9E, stop:1 #6797C7);
                border-bottom: 1px solid #325C86;
            }
            QProgressBar#modalBar {
                background: #E2E8F0;
                border: 1px solid #BDC8D6;
                border-radius: 5px;
                height: 12px;
            }
            QProgressBar#modalBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                            stop:0 #2B6CB0, stop:1 #56A3EB);
                border-radius: 4px;
            }
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top Disco banner
        banner = QFrame(self)
        banner.setObjectName("modalBanner")
        banner.setFixedHeight(34)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(14, 0, 14, 0)
        lbl_brand = QLabel("Disco - Lite")
        lbl_brand.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 700;")
        lbl_group = QLabel("by Kelompok 7")
        lbl_group.setStyleSheet("color: #E3EFFB; font-size: 10px; font-weight: 600;")
        b_layout.addWidget(lbl_brand)
        b_layout.addStretch(1)
        b_layout.addWidget(lbl_group)
        outer.addWidget(banner)

        # Body
        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 14)
        body.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        self._spinner = _DiscoSpinnerWidget(self)
        top_row.addWidget(self._spinner)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        self.lbl_title = QLabel("Importing Event Data…")
        self.lbl_title.setStyleSheet(
            "color: #1E2226; font-size: 14px; font-weight: 700;"
        )
        self.lbl_stage = QLabel("Preparing reader…")
        self.lbl_stage.setWordWrap(True)
        self.lbl_stage.setStyleSheet("color: #555E68; font-size: 11px;")
        text_col.addWidget(self.lbl_title)
        text_col.addWidget(self.lbl_stage)
        top_row.addLayout(text_col, 1)
        body.addLayout(top_row)

        self.progress = QProgressBar(self)
        self.progress.setObjectName("modalBar")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        body.addWidget(self.progress)

        foot = QHBoxLayout()
        lbl_wait = QLabel("Please wait while the event log is processed…")
        lbl_wait.setStyleSheet("color: #7A828C; font-size: 10px;")
        self.lbl_elapsed = QLabel("Elapsed: 00:00")
        self.lbl_elapsed.setStyleSheet(
            "color: #495057; font-size: 10px; font-weight: 600;"
        )
        foot.addWidget(lbl_wait, 1)
        foot.addWidget(self.lbl_elapsed)
        body.addLayout(foot)

        outer.addLayout(body, 1)

    def start(self, title: str, stage: str = "Processing…") -> None:
        self.lbl_title.setText(title)
        self.lbl_stage.setText(stage)
        self._start_ts = time.monotonic()
        self.lbl_elapsed.setText("Elapsed: 00:00")

        if self.parentWidget() is not None:
            parent_geo = self.parentWidget().window().frameGeometry()
            self.move(
                parent_geo.center().x() - self.width() // 2,
                parent_geo.center().y() - self.height() // 2,
            )

        self._timer.start()
        self.show()
        self.raise_()

    def update_stage(self, stage: str) -> None:
        self.lbl_stage.setText(stage)

    def finish(self) -> None:
        self._timer.stop()
        self.hide()

    def reject(self) -> None:
        # Prevent Esc from closing the modal while background thread is active
        if self._timer.isActive():
            return
        super().reject()

    def _on_tick(self) -> None:
        self._spinner.advance()
        elapsed = max(0, int(time.monotonic() - self._start_ts))
        mins, secs = divmod(elapsed, 60)
        self.lbl_elapsed.setText(f"Elapsed: {mins:02d}:{secs:02d}")


__all__ = ["DiscoLoadingDialog"]
