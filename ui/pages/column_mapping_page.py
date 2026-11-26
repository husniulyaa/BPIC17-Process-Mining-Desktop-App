"""Fluxicon Disco-inspired Column Configuration & Universal Data Mapping page.

Reproduces Disco's interactive column mapping screen:
- Top steel-blue gradient ribbon showing the active column name, 'column is used'
  badge, and vector-icon role buttons (Exclude, Case, Activity, Timestamp,
  Resource / Person, Lifecycle, Other).
- Interactive data preview table where clicking any column header or cell
  highlights the entire column in Disco Royal Blue (#2B5B9E) with white text.
- Bottom bar with File encoding, Delimiter, Use quotes, Timestamp format,
  validation indicator, and 'Apply & Load Workspace' action.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRect, QRectF, Qt, Signal
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
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from utils.tabular_importer import (
    ROLE_ACTIVITY,
    ROLE_CASE,
    ROLE_IGNORE,
    ROLE_LIFECYCLE,
    ROLE_OTHER,
    ROLE_RESOURCE,
    ROLE_TIMESTAMP,
    TIMESTAMP_FORMATS,
    detect_column_roles,
    is_csv_like_path,
)

ROLE_HEADER_BADGES: dict[str, str] = {
    ROLE_CASE: "🏷",
    ROLE_ACTIVITY: "✉",
    ROLE_TIMESTAMP: "🕒",
    ROLE_RESOURCE: "👥",
    ROLE_LIFECYCLE: "🔄",
    ROLE_OTHER: "💬",
    ROLE_IGNORE: "✖",
}

ROLE_DISPLAY_NAMES: dict[str, str] = {
    ROLE_CASE: "Case ID",
    ROLE_ACTIVITY: "Activity",
    ROLE_TIMESTAMP: "Timestamp",
    ROLE_RESOURCE: "Resource / Person",
    ROLE_LIFECYCLE: "Lifecycle",
    ROLE_OTHER: "Other Attribute",
    ROLE_IGNORE: "Excluded",
}

DELIMITER_CHOICES: list[tuple[str, str]] = [
    ("Auto-detect", "auto"),
    ("Comma (,)", ","),
    ("Semicolon (;)", ";"),
    ("Tab (\\t)", "\t"),
    ("Pipe (|)", "|"),
]


class _DiscoRoleButton(QPushButton):
    """Custom-painted Fluxicon Disco role icon button on the blue top banner."""

    def __init__(
        self,
        role_key: str,
        caption: str,
        tooltip: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.role_key = role_key
        self._caption = caption
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(72, 68)
        self.setToolTip(tooltip)

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)

        checked = self.isChecked()
        hovered = self.underMouse()

        if checked:
            bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            bg.setColorAt(0.0, QColor("#3E70A3"))
            bg.setColorAt(1.0, QColor("#2D5A88"))
            painter.setPen(QPen(QColor("#234970"), 1.3))
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, 7.0, 7.0)
        elif hovered:
            painter.setPen(QPen(QColor(255, 255, 255, 95), 1.0))
            painter.setBrush(QColor(255, 255, 255, 38))
            painter.drawRoundedRect(rect, 7.0, 7.0)

        cx = rect.center().x()
        cy = rect.top() + 24.0
        fg = QColor("#FFFFFF") if checked else QColor(255, 255, 255, 235)

        self._draw_icon(painter, cx, cy, fg)

        font = QFont("Segoe UI", 8, QFont.Weight.Bold if checked else QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor("#FFFFFF") if checked else QColor("#EEF5FC"))
        painter.drawText(
            QRectF(rect.left(), rect.bottom() - 20.0, rect.width(), 18.0),
            int(Qt.AlignmentFlag.AlignCenter),
            self._caption,
        )

    def _draw_icon(self, painter: QPainter, cx: float, cy: float, fg: QColor) -> None:
        painter.save()
        if self.role_key == ROLE_IGNORE:
            pen = QPen(fg, 4.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(cx - 9, cy - 9), QPointF(cx + 9, cy + 9))
            painter.drawLine(QPointF(cx + 9, cy - 9), QPointF(cx - 9, cy + 9))

        elif self.role_key == ROLE_CASE:
            # Tag silhouette with ID hole
            painter.translate(cx, cy)
            painter.rotate(-35)
            tag = QPainterPath()
            tag.moveTo(-12, -8)
            tag.lineTo(5, -8)
            tag.lineTo(13, 0)
            tag.lineTo(5, 8)
            tag.lineTo(-12, 8)
            tag.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            painter.drawPath(tag)
            painter.setBrush(QColor("#4D7CAE"))
            painter.drawEllipse(QPointF(6.5, 0), 2.3, 2.3)
            f = QFont("Segoe UI", 6, QFont.Weight.Bold)
            painter.setFont(f)
            painter.setPen(QColor("#366494"))
            painter.drawText(QRectF(-10, -7, 14, 14), int(Qt.AlignmentFlag.AlignCenter), "ID")

        elif self.role_key == ROLE_ACTIVITY:
            # Envelope icon (Disco's Activity symbol)
            env = QRectF(cx - 13, cy - 9, 26, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            painter.drawRoundedRect(env, 2.5, 2.5)
            painter.setPen(QPen(QColor("#4C7CAE"), 1.8))
            painter.drawLine(QPointF(env.left() + 1, env.top() + 1), QPointF(cx, cy + 2))
            painter.drawLine(QPointF(env.right() - 1, env.top() + 1), QPointF(cx, cy + 2))

        elif self.role_key == ROLE_TIMESTAMP:
            # Clock icon
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            painter.drawEllipse(QPointF(cx, cy), 12.0, 12.0)
            painter.setPen(QPen(QColor("#4272A4"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(cx, cy), QPointF(cx, cy - 7.0))
            painter.drawLine(QPointF(cx, cy), QPointF(cx + 5.5, cy + 2.5))

        elif self.role_key == ROLE_RESOURCE:
            # Two people silhouettes (Person / Resource)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            # Left person
            painter.drawEllipse(QPointF(cx - 5.5, cy - 7.5), 4.0, 4.0)
            painter.drawRoundedRect(QRectF(cx - 10.5, cy - 2.0, 10.0, 12.0), 3.0, 3.0)
            # Right person
            painter.drawEllipse(QPointF(cx + 6.0, cy - 6.5), 3.6, 3.6)
            painter.drawRoundedRect(QRectF(cx + 1.5, cy - 1.5, 9.0, 11.5), 3.0, 3.0)

        elif self.role_key == ROLE_LIFECYCLE:
            # Circular transition arrows
            pen = QPen(fg, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            arc_rect = QRectF(cx - 10, cy - 10, 20, 20)
            painter.drawArc(arc_rect, 35 * 16, 125 * 16)
            painter.drawArc(arc_rect, 215 * 16, 125 * 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            painter.drawPolygon(
                QPolygonF([QPointF(cx + 10, cy - 2), QPointF(cx + 5, cy - 6), QPointF(cx + 12, cy - 8)])
            )
            painter.drawPolygon(
                QPolygonF([QPointF(cx - 10, cy + 2), QPointF(cx - 5, cy + 6), QPointF(cx - 12, cy + 8)])
            )

        else:
            # Speech bubble with asterisk (Other attribute)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fg)
            painter.drawEllipse(QPointF(cx, cy - 1.5), 12.5, 10.0)
            tail = QPolygonF(
                [QPointF(cx - 6, cy + 6), QPointF(cx - 11, cy + 12), QPointF(cx - 1, cy + 8)]
            )
            painter.drawPolygon(tail)
            f = QFont("Segoe UI", 12, QFont.Weight.Bold)
            painter.setFont(f)
            painter.setPen(QColor("#4373A5"))
            painter.drawText(
                QRectF(cx - 10, cy - 9, 20, 18),
                int(Qt.AlignmentFlag.AlignCenter),
                "*",
            )
        painter.restore()


class _DiscoBannerFrame(QFrame):
    """Paints the signature Fluxicon Disco steel-blue column header ribbon."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(92)
        self._col_name = "No column selected"
        self._role = ROLE_OTHER

    def set_column_state(self, col_name: str, role: str) -> None:
        self._col_name = col_name or "No column selected"
        self._role = role
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())

        # Steel-blue horizontal gradient background
        bg = QLinearGradient(rect.topLeft(), rect.topRight())
        bg.setColorAt(0.0, QColor("#5A89BC"))
        bg.setColorAt(0.5, QColor("#7CA3CE"))
        bg.setColorAt(1.0, QColor("#A6C2E1"))
        painter.fillRect(rect, bg)

        # Left chevron arrow ribbon (matching Disco screenshot!)
        chev_w = 240.0
        h = rect.height()
        ribbon = QPolygonF(
            [
                QPointF(0.0, 0.0),
                QPointF(chev_w - 28.0, 0.0),
                QPointF(chev_w, h / 2.0),
                QPointF(chev_w - 28.0, h),
                QPointF(0.0, h),
            ]
        )
        rib_grad = QLinearGradient(0, 0, chev_w, 0)
        rib_grad.setColorAt(0.0, QColor("#4A79AC"))
        rib_grad.setColorAt(1.0, QColor("#5888BC"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(rib_grad)
        painter.drawPolygon(ribbon)

        # Crisp white chevron separator line
        painter.setPen(QPen(QColor(255, 255, 255, 190), 1.6))
        painter.drawLine(QPointF(chev_w - 28.0, 0.0), QPointF(chev_w, h / 2.0))
        painter.drawLine(QPointF(chev_w, h / 2.0), QPointF(chev_w - 28.0, h))

        # Selected column title inside left ribbon
        title_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QColor("#FFFFFF"))
        fm = QFontMetrics(title_font)
        elided = fm.elidedText(self._col_name, Qt.TextElideMode.ElideRight, int(chev_w - 48))
        painter.drawText(
            QRectF(18.0, 16.0, chev_w - 48.0, 28.0),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )

        # Status pill ('✔ column is used' or '✖ column is excluded')
        used = self._role != ROLE_IGNORE
        pill_rect = QRectF(18.0, 49.0, 148.0, 24.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#39689A") if used else QColor("#7A4545"))
        painter.drawRoundedRect(pill_rect, 11.0, 11.0)

        # White circle check/cross icon
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(pill_rect.left() + 12.0, pill_rect.center().y()), 7.0, 7.0)
        icon_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(icon_font)
        painter.setPen(QColor("#39689A") if used else QColor("#7A4545"))
        painter.drawText(
            QRectF(pill_rect.left() + 5.0, pill_rect.top() + 5.0, 14.0, 14.0),
            int(Qt.AlignmentFlag.AlignCenter),
            "✓" if used else "✕",
        )

        pill_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        painter.setFont(pill_font)
        painter.setPen(QColor("#F0F6FC"))
        role_txt = f"column is used ({ROLE_DISPLAY_NAMES.get(self._role, '')})" if used else "column is excluded"
        fm_p = QFontMetrics(pill_font)
        pill_w = max(136.0, min(chev_w - 42.0, float(fm_p.horizontalAdvance(role_txt) + 34)))
        pill_rect.setWidth(pill_w)
        # Re-draw pill background to fit role label cleanly
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#39689A") if used else QColor("#7A4545"))
        painter.drawRoundedRect(pill_rect, 11.0, 11.0)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QPointF(pill_rect.left() + 12.0, pill_rect.center().y()), 7.0, 7.0)
        painter.setFont(icon_font)
        painter.setPen(QColor("#39689A") if used else QColor("#7A4545"))
        painter.drawText(
            QRectF(pill_rect.left() + 5.0, pill_rect.top() + 5.0, 14.0, 14.0),
            int(Qt.AlignmentFlag.AlignCenter),
            "✓" if used else "✕",
        )
        painter.setFont(pill_font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(
            QRectF(pill_rect.left() + 24.0, pill_rect.top(), pill_rect.width() - 28.0, pill_rect.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm_p.elidedText(role_txt, Qt.TextElideMode.ElideRight, int(pill_rect.width() - 28)),
        )

        # Bottom border
        painter.setPen(QPen(QColor("#436A94"), 1.0))
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())


class _ColumnPreviewTableModel(QAbstractTableModel):
    """Preview model highlighting the active column in Disco Royal Blue (#2B5B9E)."""

    MAX_PREVIEW_ROWS = 250

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._df = pd.DataFrame()
        self._roles: dict[str, str] = {}
        self._active_col: int = 0

    def set_preview(
        self,
        df: pd.DataFrame | None,
        roles: dict[str, str],
        active_col: int = 0,
    ) -> None:
        self.beginResetModel()
        self._df = (
            df.head(self.MAX_PREVIEW_ROWS).copy()
            if df is not None and not df.empty
            else pd.DataFrame()
        )
        self._roles = dict(roles)
        self._active_col = max(0, min(active_col, max(0, self._df.shape[1] - 1)))
        self.endResetModel()

    def set_role(self, col_idx: int, role: str) -> None:
        if 0 <= col_idx < self._df.shape[1]:
            col_name = str(self._df.columns[col_idx])
            self._roles[col_name] = role
            self.headerDataChanged.emit(Qt.Orientation.Horizontal, col_idx, col_idx)
            if self.rowCount() > 0:
                self.dataChanged.emit(
                    self.index(0, col_idx),
                    self.index(self.rowCount() - 1, col_idx),
                )

    def set_active_column(self, col_idx: int) -> None:
        if col_idx == self._active_col or not (0 <= col_idx < self._df.shape[1]):
            return
        old = self._active_col
        self._active_col = col_idx
        self.headerDataChanged.emit(
            Qt.Orientation.Horizontal, min(old, col_idx), max(old, col_idx)
        )
        if self.rowCount() > 0:
            self.dataChanged.emit(self.index(0, old), self.index(self.rowCount() - 1, old))
            self.dataChanged.emit(
                self.index(0, col_idx), self.index(self.rowCount() - 1, col_idx)
            )

    def active_column_index(self) -> int:
        return self._active_col

    def column_name(self, col_idx: int) -> str:
        if 0 <= col_idx < self._df.shape[1]:
            return str(self._df.columns[col_idx])
        return ""

    def column_role(self, col_idx: int) -> str:
        name = self.column_name(col_idx)
        return self._roles.get(name, ROLE_OTHER)

    def roles(self) -> dict[str, str]:
        return dict(self._roles)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else self._df.shape[1]

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)
            return None

        if not (0 <= section < self._df.shape[1]):
            return None

        col_name = str(self._df.columns[section])
        col_role = self._roles.get(col_name, ROLE_OTHER)
        badge = ROLE_HEADER_BADGES.get(col_role, "💬")

        if role == Qt.ItemDataRole.DisplayRole:
            return f"{badge}  {col_name}"
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"Column: {col_name}\nAssigned Role: {ROLE_DISPLAY_NAMES.get(col_role, col_role)}"
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            val = self._df.iat[index.row(), index.column()]
            if pd.isna(val):
                return ""
            if isinstance(val, pd.Timestamp):
                return val.strftime("%Y-%m-%d %H:%M:%S")
            return str(val)

        return None


class _DiscoColumnHeaderView(QHeaderView):
    """Custom horizontal header painting the active column header blue with white text."""

    def __init__(
        self,
        model: _ColumnPreviewTableModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._preview_model = model
        self.setSectionsClickable(True)
        self.setHighlightSections(False)
        self.setStretchLastSection(True)
        self.setMinimumHeight(28)

    def paintSection(
        self,
        painter: QPainter,
        rect: QRect,
        logicalIndex: int,  # noqa: N803
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        is_active = logicalIndex == self._preview_model.active_column_index()
        col_role = self._preview_model.column_role(logicalIndex)

        if is_active:
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor("#295FA6"))
            grad.setColorAt(1.0, QColor("#1D467D"))
            painter.fillRect(rect, grad)
            painter.setPen(QColor("#163661"))
            painter.drawLine(rect.topRight(), rect.bottomRight())
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            fg = QColor("#FFFFFF")
        else:
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, QColor("#F8F9FA"))
            grad.setColorAt(1.0, QColor("#E2E5E9"))
            painter.fillRect(rect, grad)
            painter.setPen(QColor("#C6CBD1"))
            painter.drawLine(rect.topRight(), rect.bottomRight())
            painter.setPen(QColor("#B6BCC4"))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            fg = QColor("#8D959E") if col_role == ROLE_IGNORE else QColor("#24292E")

        text = str(
            self._preview_model.headerData(
                logicalIndex,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            or ""
        )
        font = QFont("Segoe UI", 9, QFont.Weight.Bold if is_active else QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(fg)
        fm = QFontMetrics(font)
        padded = rect.adjusted(8, 0, -8, 0)
        painter.drawText(
            padded,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            fm.elidedText(text, Qt.TextElideMode.ElideRight, max(20, padded.width())),
        )
        painter.restore()


class _DiscoColumnCellDelegate(QStyledItemDelegate):
    """Paints cells directly so global QSS never hides active-column blue/white styling."""

    def __init__(
        self,
        model: _ColumnPreviewTableModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._preview_model = model

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()
        rect = option.rect
        row = index.row()
        col = index.column()

        is_active = col == self._preview_model.active_column_index()
        col_role = self._preview_model.column_role(col)

        if is_active:
            bg = QColor("#2B5EA3") if row % 2 == 0 else QColor("#255392")
            fg = QColor("#FFFFFF")
            grid_pen = QColor("#1F477E")
        elif col_role == ROLE_IGNORE:
            bg = QColor("#F2F4F7") if row % 2 == 0 else QColor("#ECEFF3")
            fg = QColor("#929AA3")
            grid_pen = QColor("#E2E6EB")
        else:
            bg = QColor("#FFFFFF") if row % 2 == 0 else QColor("#F5F8FC")
            fg = QColor("#1E2226")
            grid_pen = QColor("#E8ECF1")

        painter.fillRect(rect, bg)
        painter.setPen(grid_pen)
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        if text:
            font = QFont(option.font)
            font.setPointSize(9)
            if is_active:
                font.setWeight(QFont.Weight.DemiBold)
            elif col_role == ROLE_IGNORE:
                font.setItalic(True)
            painter.setFont(font)
            painter.setPen(fg)
            fm = QFontMetrics(font)
            text_rect = rect.adjusted(8, 0, -8, 0)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                fm.elidedText(text, Qt.TextElideMode.ElideRight, max(16, text_rect.width())),
            )

        painter.restore()


class ColumnMappingPage(QWidget):
    """Interactive Fluxicon Disco Column Mapping & Import Configuration page."""

    mapping_applied = Signal(object, dict, str, str)  # raw_df, role_map, ts_fmt, source_path
    reload_csv_requested = Signal(str, str, str, bool)  # path, encoding, delimiter, use_quotes
    open_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._raw_df: pd.DataFrame | None = None
        self._source_path: str = ""
        self._is_csv_source = False

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 1. Top Steel-Blue Disco Ribbon with Role Icon Buttons
        self.banner = _DiscoBannerFrame(self)
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(258, 10, 18, 10)
        banner_layout.setSpacing(6)

        self.role_group = QButtonGroup(self)
        self.role_group.setExclusive(True)
        self._role_buttons: dict[str, _DiscoRoleButton] = {}

        role_specs = [
            (ROLE_IGNORE, "Exclude", "Ignore / exclude this column from the event log"),
            (ROLE_CASE, "Case", "Assign as Case ID (case:concept:name)"),
            (ROLE_ACTIVITY, "Activity", "Assign as Activity name (concept:name)"),
            (ROLE_TIMESTAMP, "Timestamp", "Assign as Event Timestamp (time:timestamp)"),
            (ROLE_RESOURCE, "Resource", "Assign as Person / Resource (org:resource)"),
            (ROLE_LIFECYCLE, "Lifecycle", "Assign as Lifecycle Transition (lifecycle:transition)"),
            (ROLE_OTHER, "Other", "Keep as an additional event attribute"),
        ]
        for idx, (r_key, r_label, r_tip) in enumerate(role_specs):
            btn = _DiscoRoleButton(r_key, r_label, r_tip, self.banner)
            self.role_group.addButton(btn, idx)
            self._role_buttons[r_key] = btn
            btn.clicked.connect(lambda _c=False, k=r_key: self._assign_role_to_active(k))
            banner_layout.addWidget(btn)

        banner_layout.addStretch(1)

        # Quick helper hint on right side of blue banner
        lbl_hint = QLabel(
            "Click any column below to select it,\nthen choose its role icon on this bar."
        )
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_hint.setStyleSheet("color: #1F3F63; font-size: 11px; font-weight: 600;")
        banner_layout.addWidget(lbl_hint)

        root.addWidget(self.banner)

        # 2. Center Preview Table (with full-column Disco blue highlight)
        self.model = _ColumnPreviewTableModel(self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.header_view = _DiscoColumnHeaderView(self.model, self.table)
        self.table.setHorizontalHeader(self.header_view)
        self.cell_delegate = _DiscoColumnCellDelegate(self.model, self.table)
        self.table.setItemDelegate(self.cell_delegate)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background: #EAEEF2; color: #555D65; "
            "border-right: 1px solid #C8CDD3; border-bottom: 1px solid #DCDFE4; "
            "padding: 2px 6px; font-size: 10px; }"
        )
        self.header_view.sectionClicked.connect(self._select_column)
        self.table.clicked.connect(lambda idx: self._select_column(idx.column()))
        root.addWidget(self.table, 1)

        # 3. Bottom Disco Import Configuration Bar (matching screenshot!)
        bot_bar = QFrame(self)
        bot_bar.setObjectName("discoSubBar")
        bot_layout = QHBoxLayout(bot_bar)
        bot_layout.setContentsMargins(14, 7, 14, 7)
        bot_layout.setSpacing(10)

        self.btn_open_other = QPushButton("Choose Data File…")
        self.btn_open_other.setObjectName("toolbarBtn")
        self.btn_open_other.clicked.connect(self.open_file_requested.emit)
        bot_layout.addWidget(self.btn_open_other)

        self.btn_autodetect = QPushButton("Auto-Detect Roles")
        self.btn_autodetect.setObjectName("toolbarBtn")
        self.btn_autodetect.setEnabled(False)
        self.btn_autodetect.clicked.connect(self._reset_auto_roles)
        bot_layout.addWidget(self.btn_autodetect)

        bot_layout.addWidget(QLabel("File encoding:"))
        self.combo_encoding = QComboBox()
        self.combo_encoding.addItems(["UTF-8", "UTF-8-SIG", "ISO-8859-1", "CP1252"])
        self.combo_encoding.currentIndexChanged.connect(self._on_csv_option_changed)
        bot_layout.addWidget(self.combo_encoding)

        bot_layout.addWidget(QLabel("Delimiter:"))
        self.combo_delimiter = QComboBox()
        for label_txt, _sep in DELIMITER_CHOICES:
            self.combo_delimiter.addItem(label_txt)
        self.combo_delimiter.currentIndexChanged.connect(self._on_csv_option_changed)
        bot_layout.addWidget(self.combo_delimiter)

        self.chk_quotes = QCheckBox("Use quotes")
        self.chk_quotes.setChecked(True)
        self.chk_quotes.toggled.connect(self._on_csv_option_changed)
        bot_layout.addWidget(self.chk_quotes)

        bot_layout.addWidget(QLabel("Timestamp pattern:"))
        self.combo_ts_format = QComboBox()
        self.combo_ts_format.addItems(list(TIMESTAMP_FORMATS.keys()))
        bot_layout.addWidget(self.combo_ts_format)

        bot_layout.addStretch(1)

        self.lbl_validation = QLabel("Load a CSV, Excel, XML/XMX, JSON, or XES file to configure columns.")
        self.lbl_validation.setStyleSheet("font-weight: 600; color: #4A525A;")
        bot_layout.addWidget(self.lbl_validation)

        self.btn_apply = QPushButton("Start Import / Apply Mapping  ▸")
        self.btn_apply.setObjectName("primaryActionBtn")
        self.btn_apply.setEnabled(False)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        bot_layout.addWidget(self.btn_apply)

        root.addWidget(bot_bar)
        self._set_csv_controls_enabled(False)

    # ------------------------------------------------------------ public API
    def set_raw_dataframe(
        self,
        df: pd.DataFrame | None,
        *,
        source_path: str = "",
        initial_roles: dict[str, str] | None = None,
    ) -> None:
        """Load a DataFrame into the Disco column mapper for role configuration."""
        self._raw_df = df
        self._source_path = source_path
        self._is_csv_source = bool(source_path and is_csv_like_path(source_path))
        self._set_csv_controls_enabled(self._is_csv_source)

        if df is None or df.empty:
            self.model.set_preview(None, {})
            self.banner.set_column_state("No column selected", ROLE_IGNORE)
            self.btn_autodetect.setEnabled(False)
            self.btn_apply.setEnabled(False)
            self.lbl_validation.setText("No dataset loaded.")
            return

        sample_df = df.head(250)
        roles = dict(initial_roles) if initial_roles else detect_column_roles(sample_df)
        self.model.set_preview(sample_df, roles, active_col=0)
        for c in range(self.model.columnCount()):
            col_name = self.model.column_name(c)
            est_w = min(265, max(145, len(col_name) * 8 + 48))
            self.table.setColumnWidth(c, est_w)

        self.btn_autodetect.setEnabled(True)
        self._select_column(0)
        self._update_validation_state()

    def current_csv_options(self) -> tuple[str, str, bool]:
        encoding = self.combo_encoding.currentText().lower()
        delim_idx = self.combo_delimiter.currentIndex()
        delimiter = DELIMITER_CHOICES[delim_idx][1] if 0 <= delim_idx < len(DELIMITER_CHOICES) else "auto"
        return encoding, delimiter, self.chk_quotes.isChecked()

    # ------------------------------------------------------------ internals
    def _set_csv_controls_enabled(self, enabled: bool) -> None:
        self.combo_encoding.setEnabled(enabled)
        self.combo_delimiter.setEnabled(enabled)
        self.chk_quotes.setEnabled(enabled)

    def _select_column(self, col_idx: int) -> None:
        if self._raw_df is None or not (0 <= col_idx < self.model.columnCount()):
            return
        self.model.set_active_column(col_idx)
        self.header_view.viewport().update()
        self.table.viewport().update()
        col_name = self.model.column_name(col_idx)
        role = self.model.roles().get(col_name, ROLE_OTHER)
        self.banner.set_column_state(col_name, role)
        if role in self._role_buttons:
            self._role_buttons[role].setChecked(True)

    def _assign_role_to_active(self, role_key: str) -> None:
        if self._raw_df is None or self.model.columnCount() == 0:
            return
        col_idx = self.model.active_column_index()
        col_name = self.model.column_name(col_idx)

        # Cardinality Rule 1: Exactly 1 Case ID column per event (demote previous Case column to Other)
        if role_key == ROLE_CASE:
            current_roles = self.model.roles()
            for other_idx in range(self.model.columnCount()):
                if other_idx != col_idx:
                    other_name = self.model.column_name(other_idx)
                    if current_roles.get(other_name) == ROLE_CASE:
                        self.model.set_role(other_idx, ROLE_OTHER)

        self.model.set_role(col_idx, role_key)
        self.header_view.viewport().update()
        self.table.viewport().update()
        self.banner.set_column_state(col_name, role_key)
        self._update_validation_state()

    def _reset_auto_roles(self) -> None:
        if self._raw_df is None or self._raw_df.empty:
            return
        sample_df = self._raw_df.head(250)
        roles = detect_column_roles(sample_df)
        active = self.model.active_column_index()
        self.model.set_preview(sample_df, roles, active_col=active)
        self._select_column(active)
        self._update_validation_state()

    def _update_validation_state(self) -> None:
        if self._raw_df is None or self._raw_df.empty:
            self.btn_apply.setEnabled(False)
            return

        roles = self.model.roles()
        vals = list(roles.values())
        case_cnt = vals.count(ROLE_CASE)
        act_cnt = vals.count(ROLE_ACTIVITY)
        ts_cnt = vals.count(ROLE_TIMESTAMP)

        issues = []
        if case_cnt != 1:
            issues.append(f"Case ID must be = 1 (currently {case_cnt})")
        if act_cnt < 1:
            issues.append("Activity must be ≥ 1")
        if ts_cnt < 1:
            issues.append("Timestamp must be ≥ 1")

        if issues:
            self.lbl_validation.setText("⚠ Cardinality rule: " + " · ".join(issues))
            self.lbl_validation.setStyleSheet("font-weight: 700; color: #A64B00;")
            self.btn_apply.setEnabled(False)
        else:
            ts_mode = (
                "Start + Complete → Service & Waiting Time"
                if ts_cnt >= 2
                else "1 Timestamp → Waiting Time"
            )
            self.lbl_validation.setText(
                f"✓ Valid (Case = 1 · Activity = {act_cnt} · Timestamp = {ts_cnt} [{ts_mode}])"
            )
            self.lbl_validation.setStyleSheet("font-weight: 700; color: #1E7038;")
            self.btn_apply.setEnabled(True)

    def _on_csv_option_changed(self, *_args: Any) -> None:
        if not self._is_csv_source or not self._source_path:
            return
        enc, delim, quotes = self.current_csv_options()
        self.reload_csv_requested.emit(self._source_path, enc, delim, quotes)

    def _on_apply_clicked(self) -> None:
        if self._raw_df is None or self._raw_df.empty:
            return
        roles = self.model.roles()
        ts_fmt = self.combo_ts_format.currentText()
        self.mapping_applied.emit(self._raw_df, roles, ts_fmt, self._source_path)


__all__ = ["ColumnMappingPage"]
