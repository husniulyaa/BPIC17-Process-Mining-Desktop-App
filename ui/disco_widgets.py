"""Shared Fluxicon Disco-inspired styling and custom PySide6 widgets.

Provides a cohesive silver/charcoal/steel-blue visual system modeled after
Fluxicon Disco:
- Metallic top header and segmented folder tabs
- Left master-detail sidebar lists with steel-blue active selection & chevron
- Dark charcoal chart canvas (area timeline, histogram, horizontal bars)
- Right-aligned KPI summary panel with leader lines
- Inline proportional blue data-bar delegate for QTableView
- Segmented pill toggle (e.g. Graph | Table)
- Vertical step-by-step Case Trace Graph widget with duration pills
"""

from __future__ import annotations

from typing import Any, Sequence

from PySide6.QtCore import QModelIndex, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

DISCO_COLORS = {
    "chrome_top": "#E6E6E6",
    "chrome_bot": "#CECECE",
    "chrome_border": "#9E9E9E",
    "subbar_bg": "#EFEFEF",
    "subbar_border": "#C9C9C9",
    "workspace_bg": "#F5F5F5",
    "panel_bg": "#FFFFFF",
    "panel_alt": "#F9FBFD",
    "border": "#D2D6DC",
    "border_strong": "#B4BAC2",
    "text": "#22262A",
    "text_muted": "#666D75",
    "text_light": "#8A929A",
    "blue": "#2F73B7",
    "blue_hi": "#3D85CC",
    "blue_dark": "#1F548B",
    "blue_bar": "#75A5D6",
    "blue_soft": "#E7F0FA",
    "chart_top": "#262A30",
    "chart_bot": "#14171A",
    "chart_border": "#3A4048",
    "chart_fill": "#2C6FAE",
    "chart_stroke": "#56A3EB",
    "footer_top": "#787878",
    "footer_bot": "#5E5E5E",
    "footer_border": "#4A4A4A",
    "warn_bg": "#FFF8E5",
    "warn_border": "#E5C365",
    "warn_text": "#664D03",
    "cancel_bg": "#FDECEC",
    "cancel_border": "#E09494",
    "accept_bg": "#E7F6EC",
    "accept_border": "#7EC496",
    "fraud_bg": "#FFF3DE",
    "fraud_border": "#E0B25B",
}


DISCO_QSS = """
* {
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 12px;
    color: #22262A;
}

QMainWindow, QWidget#discoRoot {
    background-color: #F5F5F5;
}

QLabel {
    background: transparent;
    color: #22262A;
}

/* TOP DISCO CHROME BAR */
QFrame#discoHeader {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #E8E8E8, stop:0.5 #DADADA, stop:1 #C9C9C9);
    border-bottom: 1px solid #9A9A9A;
}

QLabel#discoBrand {
    font-size: 21px;
    font-weight: 700;
    color: #7A7A7A;
    letter-spacing: 0.5px;
}

QFrame#datasetSelectorBox {
    background: #FFFFFF;
    border: 1px solid #969696;
    border-radius: 4px;
}

QPushButton#toolbarBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FAFAFA, stop:1 #DCDCDC);
    color: #2B2B2B;
    border: 1px solid #9A9A9A;
    border-radius: 4px;
    padding: 5px 11px;
    font-weight: 600;
}

QPushButton#toolbarBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFFFFF, stop:1 #E8E8E8);
    border-color: #7A7A7A;
}

QPushButton#toolbarBtn:pressed {
    background: #CCCCCC;
}

QPushButton#toolbarBtn:disabled {
    color: #999999;
    background: #E4E4E4;
}

QPushButton#primaryActionBtn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #3E86CC, stop:1 #28639E);
    color: #FFFFFF;
    border: 1px solid #1E4E7F;
    border-radius: 4px;
    padding: 5px 13px;
    font-weight: 600;
}

QPushButton#primaryActionBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #4A93DA, stop:1 #2F6FAE);
}

QPushButton#primaryActionBtn:disabled {
    background: #B8C7D6;
    border-color: #9FB0C1;
    color: #F0F4F8;
}

/* DISCO TOP FOLDER TABS */
QPushButton#discoTab {
    background: transparent;
    color: #3A3A3A;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    padding: 8px 13px 7px 13px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#discoTab:hover:!checked {
    background: rgba(255, 255, 255, 0.45);
    color: #111111;
}

QPushButton#discoTab:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #FFFFFF, stop:1 #EFEFEF);
    color: #1A1A1A;
    border: 1px solid #9A9A9A;
    border-bottom: 1px solid #EFEFEF;
}

/* SUB-TOOLBAR */
QFrame#discoSubBar {
    background: #EFEFEF;
    border-bottom: 1px solid #CACACA;
}

/* PANELS & CARDS */
QFrame#discoWhitePanel {
    background: #FFFFFF;
    border: 1px solid #D2D6DC;
    border-radius: 5px;
}

QFrame#discoSideControlPanel {
    background: #E5E5E5;
    border-left: 1px solid #C2C2C2;
}

QFrame#discoWarnBanner {
    background: #FFF8E5;
    border: 1px solid #E5C365;
    border-radius: 4px;
}

/* SEARCH INPUT PILL */
QLineEdit#discoSearch {
    background: #FFFFFF;
    color: #22262A;
    border: 1px solid #B3B3B3;
    border-radius: 11px;
    padding: 3px 10px;
    min-height: 18px;
}

QLineEdit#discoSearch:focus {
    border: 1px solid #2F73B7;
}

/* TABLES */
QTableView {
    background: #FFFFFF;
    alternate-background-color: #F6F8FB;
    color: #22262A;
    border: 1px solid #CCCCCC;
    gridline-color: #ECEFF3;
    selection-background-color: #2F73B7;
    selection-color: #FFFFFF;
    outline: none;
}

QTableView::item {
    padding: 4px 8px;
    border: none;
}

QTableView::item:selected {
    background: #2F73B7;
    color: #FFFFFF;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #F7F7F7, stop:1 #E3E3E3);
    color: #333333;
    border: none;
    border-right: 1px solid #CCCCCC;
    border-bottom: 1px solid #BBBBBB;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 600;
}

QTableView QTableCornerButton::section {
    background: #EAEEF2;
    border: none;
    border-right: 1px solid #C8CDD3;
    border-bottom: 1px solid #BBBBBB;
}

/* SEGMENTED PILL BUTTONS */
QPushButton#segLeft, QPushButton#segMid, QPushButton#segRight {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #F5F5F5, stop:1 #DCDCDC);
    color: #333333;
    border: 1px solid #A6A6A6;
    padding: 4px 14px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#segLeft {
    border-top-left-radius: 4px;
    border-bottom-left-radius: 4px;
}

QPushButton#segMid {
    border-left: none;
}

QPushButton#segRight {
    border-left: none;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}

QPushButton#segLeft:checked, QPushButton#segMid:checked, QPushButton#segRight:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #55595E, stop:1 #34373B);
    color: #FFFFFF;
    border-color: #2B2E31;
}

/* CHART METRIC PILLS */
QPushButton#metricPill {
    background: #E3E5E8;
    color: #33383E;
    border: 1px solid #C8CCD0;
    border-radius: 9px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    text-align: left;
}

QPushButton#metricPill:hover:!checked {
    background: #D7DCE2;
}

QPushButton#metricPill:checked {
    background: #3B3F45;
    color: #FFFFFF;
    border-color: #2A2D31;
    font-weight: 600;
}

/* BOTTOM DARK ACTION FOOTER */
QFrame#discoFooter {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                stop:0 #7B7B7B, stop:1 #5F5F5F);
    border-top: 1px solid #4A4A4A;
}

QFrame#discoFooter QLabel {
    color: #F0F0F0;
    font-size: 11px;
}

QPushButton#footerBtn {
    background: rgba(255, 255, 255, 0.14);
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 0.28);
    border-radius: 4px;
    padding: 4px 11px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#footerBtn:hover {
    background: rgba(255, 255, 255, 0.25);
}

QPushButton#footerBtn:disabled {
    color: rgba(255, 255, 255, 0.42);
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
}

/* SCROLLBARS */
QScrollBar:vertical {
    background: #EFEFEF;
    width: 11px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #BDBDBD;
    min-height: 24px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #9E9E9E;
}

QScrollBar:horizontal {
    background: #EFEFEF;
    height: 11px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #BDBDBD;
    min-width: 24px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}

QSplitter::handle {
    background: #D0D0D0;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}
"""


def make_disco_search(placeholder: str = "Search...") -> QLineEdit:
    """Create a rounded Disco-style search box."""
    edit = QLineEdit()
    edit.setObjectName("discoSearch")
    edit.setPlaceholderText(placeholder)
    edit.setClearButtonEnabled(True)
    edit.setMinimumWidth(180)
    return edit


def style_disco_table(table: QTableView) -> QTableView:
    """Apply consistent Fluxicon Disco table settings."""
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(25)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setHighlightSections(False)
    table.setShowGrid(True)
    return table


class DiscoBarDelegate(QStyledItemDelegate):
    """Paints an inline proportional steel-blue bar inside numeric table cells."""

    def __init__(
        self,
        max_provider: Any = None,
        bar_color: str = "#79A7D8",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._max_provider = max_provider
        self._bar_color = QColor(bar_color)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        raw_val = index.data(Qt.ItemDataRole.UserRole)
        max_val = 0.0
        if callable(self._max_provider):
            try:
                max_val = float(self._max_provider(index.column()) or 0.0)
            except Exception:
                max_val = 0.0

        is_selected = bool(option.state & option.state.State_Selected)
        super().paint(painter, option, index)

        if raw_val is None or max_val <= 0:
            return
        try:
            numeric = float(raw_val)
        except (TypeError, ValueError):
            return
        if numeric <= 0:
            return

        ratio = min(1.0, max(0.0, numeric / max_val))
        bar_area_width = min(72, max(28, int(option.rect.width() * 0.38)))
        bar_w = max(2, int(bar_area_width * ratio))
        bar_h = max(8, option.rect.height() - 10)
        bar_x = option.rect.right() - bar_area_width - 6
        bar_y = option.rect.top() + (option.rect.height() - bar_h) // 2

        if bar_x <= option.rect.left() + 40:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        track_color = (
            QColor(255, 255, 255, 45) if is_selected else QColor(230, 236, 244)
        )
        fill_color = (
            QColor(255, 255, 255, 195) if is_selected else self._bar_color
        )
        painter.fillRect(QRect(bar_x, bar_y, bar_area_width, bar_h), track_color)
        painter.fillRect(QRect(bar_x, bar_y, bar_w, bar_h), fill_color)
        painter.restore()


class _SidebarItemDelegate(QStyledItemDelegate):
    """Renders two-line Disco master-list items with blue selection and chevron."""

    ROLE_TITLE = Qt.ItemDataRole.UserRole + 1
    ROLE_SUBTITLE = Qt.ItemDataRole.UserRole + 2
    ROLE_KEY = Qt.ItemDataRole.UserRole + 3

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QSize:
        return QSize(180, 44)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect
        is_selected = bool(option.state & option.state.State_Selected)
        is_hover = bool(option.state & option.state.State_MouseOver)

        if is_selected:
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor("#3C84C6"))
            grad.setColorAt(1.0, QColor("#29669F"))
            painter.fillRect(rect, grad)
        elif is_hover:
            painter.fillRect(rect, QColor("#EEF4FB"))
        else:
            painter.fillRect(rect, QColor("#FFFFFF"))

        painter.setPen(QColor("#E8ECEF") if not is_selected else QColor("#235688"))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        title = str(index.data(self.ROLE_TITLE) or "")
        subtitle = str(index.data(self.ROLE_SUBTITLE) or "")

        title_font = QFont(option.font)
        title_font.setBold(True)
        title_font.setPointSize(9)
        painter.setFont(title_font)
        painter.setPen(QColor("#FFFFFF") if is_selected else QColor("#22262A"))

        text_left = rect.left() + 12
        text_width = max(40, rect.width() - 32)
        fm_title = QFontMetrics(title_font)
        painter.drawText(
            QRect(text_left, rect.top() + 6, text_width, 17),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm_title.elidedText(title, Qt.TextElideMode.ElideRight, text_width),
        )

        sub_font = QFont(option.font)
        sub_font.setPointSize(8)
        painter.setFont(sub_font)
        painter.setPen(
            QColor(235, 245, 255) if is_selected else QColor("#6C737B")
        )
        fm_sub = QFontMetrics(sub_font)
        painter.drawText(
            QRect(text_left, rect.top() + 23, text_width, 15),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm_sub.elidedText(subtitle, Qt.TextElideMode.ElideRight, text_width),
        )

        # Right chevron ›
        chev_font = QFont(option.font)
        chev_font.setBold(True)
        chev_font.setPointSize(11)
        painter.setFont(chev_font)
        painter.setPen(
            QColor("#FFFFFF") if is_selected else QColor("#8C939B")
        )
        painter.drawText(
            QRect(rect.right() - 18, rect.top(), 14, rect.height()),
            int(Qt.AlignmentFlag.AlignCenter),
            "›",
        )
        painter.restore()


class DiscoSidebarList(QWidget):
    """Titled left master-detail list styled like Disco's Views / Variants / Cases."""

    item_selected = Signal(str)

    def __init__(self, header_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header_label = QLabel(header_text)
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_label.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #F3F3F3,stop:1 #DFDFDF);"
            "border: 1px solid #C5C5C5; border-bottom: none;"
            "padding: 4px 8px; font-size: 11px; font-weight: 600; color: #555555;"
        )
        layout.addWidget(self.header_label)

        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(_SidebarItemDelegate(self.list_widget))
        self.list_widget.setStyleSheet(
            "QListWidget { background: #FFFFFF; border: 1px solid #C5C5C5; outline: none; }"
        )
        self.list_widget.setMouseTracking(True)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list_widget, 1)

    def set_header(self, text: str) -> None:
        self.header_label.setText(text)

    def set_items(
        self,
        items: Sequence[tuple[str, str, str]],
        *,
        select_key: str | None = None,
    ) -> None:
        """Populate ``(key, title, subtitle)`` items."""
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            selected_row = 0
            for idx, (key, title, subtitle) in enumerate(items):
                item = QListWidgetItem()
                item.setData(_SidebarItemDelegate.ROLE_KEY, key)
                item.setData(_SidebarItemDelegate.ROLE_TITLE, title)
                item.setData(_SidebarItemDelegate.ROLE_SUBTITLE, subtitle)
                self.list_widget.addItem(item)
                if select_key is not None and key == select_key:
                    selected_row = idx
            if items:
                self.list_widget.setCurrentRow(selected_row)
        finally:
            self.list_widget.blockSignals(False)

        if items:
            current = self.list_widget.currentItem()
            if current is not None:
                self.item_selected.emit(
                    str(current.data(_SidebarItemDelegate.ROLE_KEY))
                )

    def select_key(self, key: str, *, emit_signal: bool = False) -> bool:
        target = str(key)
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item and str(item.data(_SidebarItemDelegate.ROLE_KEY)) == target:
                if not emit_signal:
                    self.list_widget.blockSignals(True)
                try:
                    self.list_widget.setCurrentRow(row)
                    self.list_widget.scrollToItem(item)
                finally:
                    if not emit_signal:
                        self.list_widget.blockSignals(False)
                return True
        return False

    def current_key(self) -> str | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return str(item.data(_SidebarItemDelegate.ROLE_KEY))

    def _on_current_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is not None:
            self.item_selected.emit(
                str(current.data(_SidebarItemDelegate.ROLE_KEY))
            )


class DiscoSegmentedToggle(QWidget):
    """Centered pill toggle (e.g., Graph | Table or Cases | Summary)."""

    changed = Signal(str)

    def __init__(
        self,
        options: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._keys: list[str] = []

        total = len(options)
        for idx, (key, caption) in enumerate(options):
            btn = QPushButton(caption)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if total == 1:
                btn.setObjectName("toolbarBtn")
            elif idx == 0:
                btn.setObjectName("segLeft")
            elif idx == total - 1:
                btn.setObjectName("segRight")
            else:
                btn.setObjectName("segMid")
            if idx == 0:
                btn.setChecked(True)
            self._group.addButton(btn, idx)
            self._buttons[key] = btn
            self._keys.append(key)
            layout.addWidget(btn)

        self._group.idClicked.connect(self._on_clicked)

    def set_label(self, key: str, text: str) -> None:
        if key in self._buttons:
            self._buttons[key].setText(text)

    def set_current(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def current_key(self) -> str:
        checked_id = self._group.checkedId()
        if 0 <= checked_id < len(self._keys):
            return self._keys[checked_id]
        return self._keys[0] if self._keys else ""

    def _on_clicked(self, idx: int) -> None:
        if 0 <= idx < len(self._keys):
            self.changed.emit(self._keys[idx])


class DiscoKpiPanel(QWidget):
    """Right-side metric summary list with Disco's clean label-line-value rows."""

    def __init__(
        self,
        metrics: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(235)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(6)

        self._value_labels: dict[str, QLabel] = {}
        for key, caption in metrics:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)

            lbl_cap = QLabel(caption)
            lbl_cap.setStyleSheet("color: #6B727A; font-size: 11px;")

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #D8DCE0; background: #D8DCE0; max-height: 1px;")
            line.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )

            lbl_val = QLabel("—")
            lbl_val.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lbl_val.setStyleSheet(
                "color: #1E2226; font-size: 14px; font-weight: 700;"
            )

            row.addWidget(lbl_cap)
            row.addWidget(line, 1)
            row.addWidget(lbl_val)

            wrapper = QWidget()
            wrapper.setLayout(row)
            layout.addWidget(wrapper)
            self._value_labels[key] = lbl_val

        layout.addStretch(1)

    def set_value(self, key: str, value: str) -> None:
        if key in self._value_labels:
            self._value_labels[key].setText(value)

    def reset(self) -> None:
        for lbl in self._value_labels.values():
            lbl.setText("—")


class DiscoDarkChart(QWidget):
    """Dark charcoal chart canvas modeled after Disco's Statistics & Case charts.

    Supports ``kind='area'`` (smooth timeline/profile curve) and ``kind='bars'``
    (vertical distribution bars).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(145)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self._values: list[float] = []
        self._labels: list[str] = []
        self._kind: str = "bars"
        self._x_caption: str = ""
        self._y_caption: str = ""
        self._empty_text: str = "Load an XES event log to view distribution"

    def set_series(
        self,
        values: Sequence[float],
        labels: Sequence[str] | None = None,
        *,
        kind: str = "bars",
        x_caption: str = "",
        y_caption: str = "",
        empty_text: str | None = None,
    ) -> None:
        self._values = [max(0.0, float(v)) for v in values]
        self._labels = [str(x) for x in labels] if labels is not None else []
        self._kind = kind
        self._x_caption = x_caption
        self._y_caption = y_caption
        if empty_text is not None:
            self._empty_text = empty_text
        self.update()

    def clear_chart(self, empty_text: str | None = None) -> None:
        self._values = []
        self._labels = []
        if empty_text is not None:
            self._empty_text = empty_text
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg_grad = QLinearGradient(outer.topLeft(), outer.bottomLeft())
        bg_grad.setColorAt(0.0, QColor(DISCO_COLORS["chart_top"]))
        bg_grad.setColorAt(1.0, QColor(DISCO_COLORS["chart_bot"]))

        painter.setPen(QPen(QColor(DISCO_COLORS["chart_border"]), 1.2))
        painter.setBrush(QBrush(bg_grad))
        painter.drawRoundedRect(outer, 7.0, 7.0)

        if not self._values or max(self._values, default=0.0) <= 0:
            painter.setPen(QColor("#8C96A0"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(
                outer,
                int(Qt.AlignmentFlag.AlignCenter),
                self._empty_text,
            )
            return

        left_pad = 32.0 if self._y_caption else 18.0
        right_pad = 16.0
        top_pad = 16.0
        bot_pad = 26.0
        plot = QRectF(
            outer.left() + left_pad,
            outer.top() + top_pad,
            max(20.0, outer.width() - left_pad - right_pad),
            max(20.0, outer.height() - top_pad - bot_pad),
        )

        # Subtle horizontal gridlines
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        for step in range(1, 4):
            gy = plot.top() + plot.height() * step / 4.0
            painter.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))

        # Baseline
        painter.setPen(QPen(QColor("#59626A"), 1.0))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())

        max_v = max(self._values) or 1.0
        n = len(self._values)

        if self._kind == "area" and n >= 2:
            path = QPainterPath()
            line_path = QPainterPath()
            path.moveTo(plot.left(), plot.bottom())
            for i, val in enumerate(self._values):
                px = plot.left() + plot.width() * i / (n - 1)
                py = plot.bottom() - (val / max_v) * (plot.height() - 4.0)
                if i == 0:
                    line_path.moveTo(px, py)
                else:
                    line_path.lineTo(px, py)
                path.lineTo(px, py)
            path.lineTo(plot.right(), plot.bottom())
            path.closeSubpath()

            area_grad = QLinearGradient(plot.topLeft(), plot.bottomLeft())
            area_grad.setColorAt(0.0, QColor(59, 134, 198, 215))
            area_grad.setColorAt(1.0, QColor(33, 82, 130, 120))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(area_grad)
            painter.drawPath(path)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(DISCO_COLORS["chart_stroke"]), 1.6))
            painter.drawPath(line_path)
        else:
            slot_w = plot.width() / max(1, n)
            bar_w = max(2.0, min(28.0, slot_w * 0.76))
            painter.setPen(Qt.PenStyle.NoPen)
            for i, val in enumerate(self._values):
                bh = (val / max_v) * (plot.height() - 2.0)
                if bh <= 0.5 and val > 0:
                    bh = 1.5
                bx = plot.left() + i * slot_w + (slot_w - bar_w) / 2.0
                by = plot.bottom() - bh
                bar_grad = QLinearGradient(bx, by, bx, plot.bottom())
                bar_grad.setColorAt(0.0, QColor("#529CE0"))
                bar_grad.setColorAt(1.0, QColor("#26639C"))
                painter.setBrush(bar_grad)
                painter.drawRect(QRectF(bx, by, bar_w, bh))

        # Captions & endpoint labels
        cap_font = painter.font()
        cap_font.setPointSize(8)
        painter.setFont(cap_font)
        painter.setPen(QColor("#9BA5B0"))

        if self._labels:
            first_lbl = self._labels[0]
            last_lbl = self._labels[-1] if len(self._labels) > 1 else ""
            painter.drawText(
                QRectF(plot.left(), plot.bottom() + 4, 140, 18),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                first_lbl,
            )
            if last_lbl:
                painter.drawText(
                    QRectF(plot.right() - 140, plot.bottom() + 4, 140, 18),
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    last_lbl,
                )

        if self._x_caption:
            painter.drawText(
                QRectF(plot.left(), plot.bottom() + 4, plot.width(), 18),
                int(Qt.AlignmentFlag.AlignCenter),
                self._x_caption,
            )

        if self._y_caption:
            painter.save()
            painter.translate(outer.left() + 13, plot.center().y())
            painter.rotate(-90)
            painter.drawText(
                QRectF(-plot.height() / 2.0, -8, plot.height(), 16),
                int(Qt.AlignmentFlag.AlignCenter),
                self._y_caption,
            )
            painter.restore()


class _TraceGraphCanvas(QWidget):
    """Internal painted canvas rendering Disco's vertical step-by-step case graph."""

    step_clicked = Signal(int)

    CARD_W = 390.0
    CARD_H = 62.0
    GAP_H = 44.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._events: list[dict[str, Any]] = []
        self._selected_idx: int = -1
        self._highlights: set[str] = set()
        self._card_rects: list[QRectF] = []
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_events(
        self,
        events: Sequence[dict[str, Any]],
        *,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        self._events = list(events)
        self._selected_idx = 0 if self._events else -1
        self._highlights = {
            str(a).strip() for a in (highlight_activities or []) if str(a).strip()
        }
        total_h = (
            int(28 + len(self._events) * (self.CARD_H + self.GAP_H))
            if self._events
            else 180
        )
        self.setMinimumHeight(max(180, total_h))
        self.setMinimumWidth(480)
        self.update()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        pos = event.position()
        for idx, rect in enumerate(self._card_rects):
            if rect.contains(pos):
                self._selected_idx = idx
                self.update()
                self.step_clicked.emit(idx)
                return
        super().mousePressEvent(event)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#F8F9FA"))

        self._card_rects = []
        if not self._events:
            painter.setPen(QColor("#7A828A"))
            painter.drawText(
                self.rect(),
                int(Qt.AlignmentFlag.AlignCenter),
                "Select a case on the left to inspect its step-by-step process flow.",
            )
            return

        cx = max(self.CARD_W / 2.0 + 36.0, self.width() / 2.0)
        y = 18.0

        for idx, ev in enumerate(self._events):
            card_rect = QRectF(
                cx - self.CARD_W / 2.0,
                y,
                self.CARD_W,
                self.CARD_H,
            )
            self._card_rects.append(card_rect)

            activity = str(ev.get("activity", ""))
            is_selected = idx == self._selected_idx

            # Choose card colors (Disco metallic neutral, or semantic highlights)
            if activity == "O_Cancelled":
                top_c, bot_c, border_c = "#FDECEC", "#F9D6D6", "#D98282"
            elif activity == "O_Accepted":
                top_c, bot_c, border_c = "#E8F7EE", "#D2EFE0", "#6CB888"
            elif activity in self._highlights or "Fraud" in activity:
                top_c, bot_c, border_c = "#FFF5E0", "#FBE8BE", "#D6A648"
            else:
                top_c, bot_c, border_c = "#EEEEEE", "#DEDEDE", "#B4B4B4"

            if is_selected:
                border_c = "#2B6CB0"

            # Step number pill attached to left of card
            badge_rect = QRectF(card_rect.left() - 26.0, y + 18.0, 26.0, 24.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#3E6B89" if not is_selected else "#24588E"))
            painter.drawRoundedRect(badge_rect, 4.0, 4.0)

            step_font = QFont(painter.font())
            step_font.setBold(True)
            step_font.setPointSize(8)
            painter.setFont(step_font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                badge_rect,
                int(Qt.AlignmentFlag.AlignCenter),
                str(ev.get("step", idx + 1)),
            )

            # Card body
            grad = QLinearGradient(card_rect.topLeft(), card_rect.bottomLeft())
            grad.setColorAt(0.0, QColor(top_c))
            grad.setColorAt(1.0, QColor(bot_c))
            painter.setPen(QPen(QColor(border_c), 2.0 if is_selected else 1.1))
            painter.setBrush(grad)
            painter.drawRoundedRect(card_rect, 6.0, 6.0)

            # Activity title
            act_font = QFont(painter.font())
            act_font.setBold(True)
            act_font.setPointSize(10)
            painter.setFont(act_font)
            painter.setPen(QColor("#1B1F23"))
            fm_act = QFontMetrics(act_font)
            painter.drawText(
                QRectF(card_rect.left() + 12, y + 7, card_rect.width() - 24, 20),
                int(Qt.AlignmentFlag.AlignCenter),
                fm_act.elidedText(
                    activity,
                    Qt.TextElideMode.ElideRight,
                    int(card_rect.width() - 24),
                ),
            )

            # Timestamp + Resource + Lifecycle lines
            meta_font = QFont(painter.font())
            meta_font.setBold(False)
            meta_font.setPointSize(8)
            painter.setFont(meta_font)
            painter.setPen(QColor("#555B62"))

            ts_text = str(ev.get("timestamp") or "timestamp unavailable")
            res_val = ev.get("resource") or ev.get("org:resource")
            line1 = f"{ts_text}" + (f"  ·  by {res_val}" if res_val else "")
            painter.drawText(
                QRectF(card_rect.left() + 12, y + 27, card_rect.width() - 24, 15),
                int(Qt.AlignmentFlag.AlignCenter),
                line1,
            )

            lc_val = ev.get("lifecycle") or ev.get("lifecycle:transition")
            role_val = ev.get("role")
            line2_parts = []
            if lc_val:
                line2_parts.append(f"lifecycle: {lc_val}")
            if role_val and role_val != "intermediate":
                line2_parts.append(role_val.replace("_", " "))
            line2 = "  ·  ".join(line2_parts) if line2_parts else "recorded event"
            painter.drawText(
                QRectF(card_rect.left() + 12, y + 42, card_rect.width() - 24, 15),
                int(Qt.AlignmentFlag.AlignCenter),
                line2,
            )

            # Connector arrow & duration pill to next event
            if idx < len(self._events) - 1:
                next_ev = self._events[idx + 1]
                arrow_top = card_rect.bottom() + 2.0
                arrow_bot = card_rect.bottom() + self.GAP_H - 3.0

                painter.setPen(QPen(QColor("#80868D"), 2.2))
                painter.drawLine(QPointF(cx, arrow_top), QPointF(cx, arrow_bot - 5.0))

                head = QPolygonF(
                    [
                        QPointF(cx, arrow_bot),
                        QPointF(cx - 5.0, arrow_bot - 7.0),
                        QPointF(cx + 5.0, arrow_bot - 7.0),
                    ]
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#80868D"))
                painter.drawPolygon(head)

                delta_txt = str(next_ev.get("delta_from_prev_display") or "")
                if delta_txt and delta_txt != "—":
                    mid_y = (arrow_top + arrow_bot) / 2.0
                    painter.setBrush(QColor("#DAE6F2"))
                    painter.setPen(QPen(QColor("#AFC4DA"), 1.0))
                    painter.drawEllipse(QPointF(cx, mid_y), 3.5, 3.5)

                    pill_font = QFont(painter.font())
                    pill_font.setPointSize(8)
                    painter.setFont(pill_font)
                    fm_pill = QFontMetrics(pill_font)
                    pw = max(54.0, float(fm_pill.horizontalAdvance(delta_txt) + 16))
                    pill_rect = QRectF(cx + 10.0, mid_y - 9.5, pw, 19.0)
                    painter.drawRoundedRect(pill_rect, 8.0, 8.0)
                    painter.setPen(QColor("#385470"))
                    painter.drawText(
                        pill_rect,
                        int(Qt.AlignmentFlag.AlignCenter),
                        delta_txt,
                    )

            y += self.CARD_H + self.GAP_H


class DiscoTraceGraphWidget(QScrollArea):
    """Scrollable Disco step-by-step case trace flow widget."""

    step_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setStyleSheet(
            "QScrollArea { background: #F8F9FA; border: 1px solid #CCCCCC; }"
        )
        self._canvas = _TraceGraphCanvas(self)
        self._canvas.step_clicked.connect(self.step_clicked.emit)
        self.setWidget(self._canvas)

    def set_events(
        self,
        events: Sequence[dict[str, Any]],
        *,
        highlight_activities: Sequence[str] | None = None,
    ) -> None:
        self._canvas.set_events(
            events,
            highlight_activities=highlight_activities,
        )
        self.verticalScrollBar().setValue(0)


__all__ = [
    "DISCO_COLORS",
    "DISCO_QSS",
    "DiscoBarDelegate",
    "DiscoDarkChart",
    "DiscoKpiPanel",
    "DiscoSearchBox",
    "DiscoSegmentedToggle",
    "DiscoSidebarList",
    "DiscoTraceGraphWidget",
    "make_disco_search",
    "style_disco_table",
]
DiscoSearchBox = make_disco_search
