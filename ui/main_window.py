
"""BPIC17 process-mining workspace (PySide6).

Integration contract:
    MainWindow.event_df
    MainWindow.set_event_data(df, path=None)
    MainWindow.dataset_requested
    MainWindow.dataset_path

This file contains no exercise algorithms.
"""

import sys
import random
import pandas as pd

from PySide6.QtCore import (
    Qt, Signal, QAbstractTableModel, QModelIndex,
    QSortFilterProxyModel, QStringListModel, QRectF
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QButtonGroup,
    QStackedWidget, QTableView, QHeaderView, QFrame,
    QFileDialog, QLineEdit, QListView, QSplitter,
    QAbstractItemView
)


C = dict(
    bg="#20251F",
    surface="#292F27",
    elevated="#343A30",
    text="#F1EDE2",
    text2="#B6B3A7",
    olive="#858B68",
    brass="#B39A68",
    brass_hi="#C6AE7C",
    brass_lo="#9A8355",
    border="#454A3E",
    ink="#1B1F19",
    ok="#8FA36B",
    err="#C08463"
)


QSS = """
* {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget#root {
    background: %(bg)s;
}

QLabel {
    color: %(text)s;
    background: transparent;
}

QLabel#muted {
    color: %(text2)s;
}

QLabel#brand {
    font-size: 22px;
    font-weight: 700;
}

QLabel#pageTitle {
    font-size: 27px;
    font-weight: 600;
}

QLabel#statValue {
    font-size: 24px;
    font-weight: 600;
}

QLabel#statKey {
    color: %(text2)s;
    font-size: 10px;
    font-weight: 600;
}

QLabel#panelTitle {
    color: %(text2)s;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}

/* HEADER & NAVIGATION */

QFrame#header {
    background: %(surface)s;
    border-bottom: 1px solid %(border)s;
    border-radius: 8px;
}

QFrame#navbar {
    background: %(bg)s;
    border-bottom: 1px solid %(border)s;
    border-radius: 8px;
}

QFrame#segment {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}

QFrame#footer {
    background: %(surface)s;
    border-top: 1px solid %(border)s;
    border-radius: 8px;
}

/* PANELS */

QFrame#panel {
    background: %(surface)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
}

QFrame#rule {
    background: %(border)s;
    max-width: 1px;
    min-width: 1px;
    border: none;
}

/* BUTTONS */

QPushButton {
    border-radius: 8px;
}

QPushButton#nav {
    background: transparent;
    color: %(text2)s;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 9px 15px;
    font-weight: 500;
}

QPushButton#nav:hover {
    background: %(elevated)s;
    color: %(text)s;
}

QPushButton#nav:pressed {
    background: %(ink)s;
}

QPushButton#nav:checked {
    background: %(elevated)s;
    color: %(text)s;
    font-weight: 600;
    border: 1px solid %(border)s;
    border-bottom: 2px solid %(brass)s;
    border-radius: 8px;
}

QPushButton#primary {
    background: %(brass)s;
    color: %(ink)s;
    border: 1px solid %(brass_hi)s;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 700;
}

QPushButton#primary:hover {
    background: %(brass_hi)s;
}

QPushButton#primary:pressed {
    background: %(brass_lo)s;
}

QPushButton:focus {
    outline: none;
}

/* INPUT */

QLineEdit {
    background: %(bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: %(brass)s;
    selection-color: %(ink)s;
}

QLineEdit:focus {
    border: 1px solid %(brass)s;
}

/* TABLES */

QTableView {
    background: %(bg)s;
    alternate-background-color: %(surface)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    gridline-color: %(border)s;
    selection-background-color: %(elevated)s;
    selection-color: %(text)s;
    outline: none;
    padding: 3px;
}

QTableView::item {
    border: none;
    padding: 5px 7px;
}

QTableView::item:selected {
    background: %(elevated)s;
    color: %(text)s;
}

QHeaderView {
    background: %(elevated)s;
    border: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QHeaderView::section {
    background: %(elevated)s;
    color: %(text2)s;
    border: none;
    border-right: 1px solid %(border)s;
    border-bottom: 1px solid %(border)s;
    border-radius: 8px;
    padding: 8px 9px;
    font-size: 10px;
    font-weight: 600;
}

/* CASE EXPLORER LIST */

QListView {
    background: %(bg)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    outline: none;
    padding: 3px;
}

QListView::item {
    padding: 7px 9px;
    border-radius: 8px;
}

QListView::item:selected {
    background: %(elevated)s;
    border-left: 2px solid %(brass)s;
}

QListView::item:hover {
    background: %(surface)s;
}

/* SCROLLBARS */

QScrollBar:vertical {
    background: %(bg)s;
    width: 11px;
    margin: 2px;
    border-radius: 8px;
}

QScrollBar::handle:vertical {
    background: %(border)s;
    min-height: 28px;
    border-radius: 8px;
}

QScrollBar::handle:vertical:hover {
    background: %(olive)s;
}

QScrollBar:horizontal {
    background: %(bg)s;
    height: 11px;
    margin: 2px;
    border-radius: 8px;
}

QScrollBar::handle:horizontal {
    background: %(border)s;
    min-width: 28px;
    border-radius: 8px;
}

QScrollBar::handle:horizontal:hover {
    background: %(olive)s;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    width: 0px;
    height: 0px;
}

/* OTHER */

QSplitter::handle {
    background: %(bg)s;
}

QToolTip {
    background: %(elevated)s;
    color: %(text)s;
    border: 1px solid %(border)s;
    border-radius: 8px;
    padding: 5px 8px;
}
""" % C


CASE_COLS = ("case:concept:name", "case_id", "case")
ACT_COLS = ("concept:name", "activity")
TIME_COLS = ("time:timestamp", "timestamp")
RES_COLS = ("org:resource", "resource")


def pick(df, names):
    if df is None:
        return None

    for name in names:
        if name in df.columns:
            return name

    return None


def fmt_dur(td):
    if pd.isna(td):
        return "—"

    d = td.days
    h = td.seconds // 3600

    return f"{d}d {h}h" if d else f"{h}h {(td.seconds % 3600) // 60}m"


class DataFrameModel(QAbstractTableModel):
    def __init__(self, df=None, limit=None):
        super().__init__()
        self._limit = limit
        self.set_df(df)

    def set_df(self, df):
        self.beginResetModel()

        if df is not None and self._limit:
            df = df.head(self._limit)

        self._df = df if df is not None else pd.DataFrame()

        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self._df.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            value = self._df.iat[index.row(), index.column()]

            if isinstance(value, pd.Timestamp):
                return value.strftime("%Y-%m-%d %H:%M:%S")

            return "" if pd.isna(value) else str(value)

        if role == Qt.ForegroundRole and index.column() == 0:
            return QColor(C["text"])

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return str(self._df.columns[section])

        return None


def make_table(model):
    table = QTableView()
    table.setModel(model)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().hide()
    table.verticalHeader().setDefaultSectionSize(28)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    table.setShowGrid(False)

    return table


def rule():
    frame = QFrame()
    frame.setObjectName("rule")
    return frame


def label(text, name=None):
    result = QLabel(text)

    if name:
        result.setObjectName(name)

    return result


class BarList(QWidget):
    """Horizontal ranked bars for activity frequency."""

    ROW = 30

    def __init__(self):
        super().__init__()
        self._items = []
        self.setMinimumWidth(300)

    def set_items(self, items):
        self._items = items
        self.setMinimumHeight(self.ROW * max(len(items), 1) + 8)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._items:
            painter.setPen(QColor(C["text2"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data")
            return

        top = max(count for _, count in self._items) or 1
        width = self.width()

        for i, (name, count) in enumerate(self._items):
            y = 4 + i * self.ROW

            painter.setPen(QColor(C["text"]))
            fm = painter.fontMetrics()

            painter.drawText(
                0, y, width - 70, 16,
                Qt.AlignLeft | Qt.AlignVCenter,
                fm.elidedText(name, Qt.ElideRight, width - 80)
            )

            painter.setPen(QColor(C["text2"]))
            painter.drawText(
                width - 68, y, 68, 16,
                Qt.AlignRight | Qt.AlignVCenter,
                f"{count:,}"
            )

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(C["border"]))
            painter.drawRoundedRect(
                QRectF(0, y + 20, width, 3), 1.5, 1.5
            )

            painter.setBrush(
                QColor(C["brass"] if i == 0 else C["olive"])
            )
            painter.drawRoundedRect(
                QRectF(0, y + 20, width * count / top, 3),
                1.5, 1.5
            )


class BasePage(QWidget):
    """Shared page layout. No automatic numbering or subtitle."""

    def __init__(self, title):
        super().__init__()

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(32, 24, 32, 20)
        self.root.setSpacing(16)

        self.root.addWidget(label(title, "pageTitle"))

    def set_event_data(self, df):
        pass


class OverviewPage(BasePage):
    def __init__(self):
        super().__init__("Dataset summary")

        strip = QFrame()
        strip.setObjectName("panel")

        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(8, 12, 8, 12)

        self._stats = {}

        keys = ["Events", "Cases", "Activities", "Resources", "Time span"]

        for i, key in enumerate(keys):
            column = QVBoxLayout()
            column.setContentsMargins(18, 0, 18, 0)
            column.setSpacing(0)

            value = label("—", "statValue")

            column.addWidget(label(key.upper(), "statKey"))
            column.addWidget(value)

            self._stats[key] = value
            strip_layout.addLayout(column, 1)

            if i < len(keys) - 1:
                strip_layout.addWidget(rule())

        self.root.addWidget(strip)

        split = QSplitter(Qt.Horizontal)

        left = QVBoxLayout()
        left.setSpacing(8)

        self.table_title = label("EVENT LOG", "panelTitle")
        left.addWidget(self.table_title)

        self.model = DataFrameModel(limit=2000)
        self.table = make_table(self.model)

        left.addWidget(self.table, 1)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left.setContentsMargins(0, 0, 8, 0)

        right = QVBoxLayout()
        right.setSpacing(8)

        right.addWidget(label("MOST FREQUENT ACTIVITIES", "panelTitle"))

        self.bars = BarList()

        bar_frame = QFrame()
        bar_frame.setObjectName("panel")

        bar_layout = QVBoxLayout(bar_frame)
        bar_layout.setContentsMargins(16, 14, 16, 10)
        bar_layout.addWidget(self.bars)
        bar_layout.addStretch(1)

        right.addWidget(bar_frame, 1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setMinimumWidth(340)
        right.setContentsMargins(8, 0, 0, 0)

        split.addWidget(left_widget)
        split.addWidget(right_widget)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)

        self.root.addWidget(split, 1)

    def set_event_data(self, df):
        self.model.set_df(df)
        self.table.resizeColumnsToContents()

        if df is None:
            for value in self._stats.values():
                value.setText("—")

            self.bars.set_items([])
            self.table_title.setText("EVENT LOG")
            return

        case = pick(df, CASE_COLS)
        activity = pick(df, ACT_COLS)
        timestamp = pick(df, TIME_COLS)
        resource = pick(df, RES_COLS)

        self._stats["Events"].setText(f"{len(df):,}")
        self._stats["Cases"].setText(
            f"{df[case].nunique():,}" if case else "—"
        )
        self._stats["Activities"].setText(
            f"{df[activity].nunique():,}" if activity else "—"
        )
        self._stats["Resources"].setText(
            f"{df[resource].nunique():,}" if resource else "—"
        )

        if timestamp:
            time_values = pd.to_datetime(df[timestamp], errors="coerce")

            self._stats["Time span"].setText(
                f"{time_values.min():%b %Y} – {time_values.max():%b %Y}"
                if time_values.notna().any() else "—"
            )

        self.bars.set_items(
            [
                (str(key), int(value))
                for key, value in df[activity].value_counts().head(12).items()
            ] if activity else []
        )

        self.table_title.setText(
            f"EVENT LOG  ·  FIRST {min(len(df), 2000):,} OF {len(df):,} EVENTS"
        )


class ExercisePage(BasePage):
    """Shell for teammate-owned analysis modules."""

    def __init__(self, exercise):
        super().__init__(f"Exercise {exercise}")

        self.exercise = exercise

        panel = QFrame()
        panel.setObjectName("panel")

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(24, 20, 24, 20)
        panel_layout.setSpacing(8)

        panel_layout.addWidget(label("STATUS", "panelTitle"))

        self.state = label("Awaiting dataset", "statValue")
        panel_layout.addWidget(self.state)

        self.detail = label(
            "Import an XES log to make event_df available to this module.",
            "muted"
        )
        self.detail.setWordWrap(True)
        panel_layout.addWidget(self.detail)

        self.cols = label("", "muted")
        self.cols.setWordWrap(True)
        panel_layout.addWidget(self.cols)

        panel_layout.addSpacing(8)

        note = label(
            f"The analysis for Exercise {exercise} is implemented by its owner. "
            "Place result widgets in this page's body layout.",
            "muted"
        )
        note.setWordWrap(True)
        panel_layout.addWidget(note)

        self.root.addWidget(panel)

        self.body = QVBoxLayout()
        self.root.addLayout(self.body)
        self.root.addStretch(1)

    def set_event_data(self, df):
        if df is None:
            self.state.setText("Awaiting dataset")
            self.detail.setText(
                "Import an XES log to make event_df available to this module."
            )
            self.cols.setText("")

        else:
            self.state.setText("Data ready")
            self.detail.setText(
                f"event_df: {len(df):,} rows × {df.shape[1]} columns"
            )
            self.cols.setText(
                "Columns: " + "  ·  ".join(map(str, df.columns))
            )


class CaseExplorerPage(BasePage):
    def __init__(self):
        super().__init__("Trace inspection")

        self._df = None
        self._index = {}

        split = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(label("CASES", "panelTitle"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter case ID…")
        self.search.setClearButtonEnabled(True)

        left_layout.addWidget(self.search)

        self.names = QStringListModel()

        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.names)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self.list = QListView()
        self.list.setModel(self.proxy)
        self.list.setEditTriggers(QAbstractItemView.NoEditTriggers)

        left_layout.addWidget(self.list, 1)

        self.count = label("", "muted")
        left_layout.addWidget(self.count)

        left_widget.setMinimumWidth(260)
        left_widget.setMaximumWidth(380)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        self.case_title = label("Select a case", "statValue")
        self.case_meta = label(
            "Pick a case from the list to see its ordered events.",
            "muted"
        )

        right_layout.addWidget(label("TRACE", "panelTitle"))
        right_layout.addWidget(self.case_title)
        right_layout.addWidget(self.case_meta)

        self.model = DataFrameModel()
        self.table = make_table(self.model)

        right_layout.addWidget(self.table, 1)

        split.addWidget(left_widget)
        split.addWidget(right_widget)

        split.setStretchFactor(1, 1)
        split.setChildrenCollapsible(False)

        self.root.addWidget(split, 1)

        self.search.textChanged.connect(self._filter)
        self.list.selectionModel().currentChanged.connect(self._select)

    def _filter(self, text):
        self.proxy.setFilterFixedString(text)
        self.count.setText(f"{self.proxy.rowCount():,} shown")

    def set_event_data(self, df):
        self._df = df
        self.model.set_df(None)

        self.case_title.setText("Select a case")
        self.case_meta.setText(
            "Pick a case from the list to see its ordered events."
        )

        case = pick(df, CASE_COLS)

        if df is None or case is None:
            self._index = {}
            self.names.setStringList([])
            self.count.setText("")
            return

        self._index = df.groupby(case, sort=False).indices

        self.names.setStringList(
            [str(key) for key in self._index]
        )

        self.count.setText(f"{len(self._index):,} cases")

    def _select(self, current, previous):
        if not current.isValid() or self._df is None:
            return

        case_id = current.data()
        rows = self._index.get(case_id)

        if rows is None:
            rows = next(
                (
                    value for key, value in self._index.items()
                    if str(key) == case_id
                ),
                None
            )

        if rows is None:
            return

        subset = self._df.iloc[rows]

        timestamp = pick(subset, TIME_COLS)

        if timestamp:
            subset = subset.sort_values(timestamp, kind="stable")

        self.model.set_df(subset)
        self.case_title.setText(str(case_id))

        meta = f"{len(subset):,} events"

        if timestamp:
            times = pd.to_datetime(subset[timestamp], errors="coerce")
            meta += f"  ·  duration {fmt_dur(times.max() - times.min())}"

        activity = pick(subset, ACT_COLS)

        if activity:
            meta += (
                f"  ·  {subset[activity].iloc[0]}"
                f" → {subset[activity].iloc[-1]}"
            )

        self.case_meta.setText(meta)
        self.table.resizeColumnsToContents()


PAGES = [
    "Overview",
    "Exercise 11.7",
    "Exercise 11.15",
    "Exercise 11.18",
    "Exercise 11.22",
    "Case Explorer"
]


class MainWindow(QMainWindow):
    dataset_requested = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("BPIC17 — Process Workspace")
        self.resize(1360, 840)
        self.setMinimumSize(1080, 640)

        self.event_df = None
        self.dataset_path = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # HEADER

        header = QFrame()
        header.setObjectName("header")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(32, 14, 32, 14)
        header_layout.setSpacing(16)

        ident = QVBoxLayout()
        ident.setSpacing(0)

        ident.addWidget(label("BPIC17", "brand"))
        ident.addWidget(
            label("LOAN APPLICATION EVENT LOG WORKSPACE", "muted")
        )

        header_layout.addLayout(ident)
        header_layout.addStretch(1)

        self.status = label("No dataset loaded", "muted")
        self.status.setTextFormat(Qt.RichText)

        header_layout.addWidget(self.status)

        self.import_btn = QPushButton("Import XES")
        self.import_btn.setObjectName("primary")
        self.import_btn.setCursor(Qt.PointingHandCursor)
        self.import_btn.clicked.connect(self._on_import)

        header_layout.addWidget(self.import_btn)

        outer.addWidget(header)

        # HORIZONTAL NAVIGATION

        navbar = QFrame()
        navbar.setObjectName("navbar")

        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(32, 12, 32, 12)

        segment = QFrame()
        segment.setObjectName("segment")

        segment_layout = QHBoxLayout(segment)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)

        self.stack = QStackedWidget()

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        self.nav_buttons = []

        self.pages = [
            OverviewPage(),
            ExercisePage("11.7"),
            ExercisePage("11.15"),
            ExercisePage("11.18"),
            ExercisePage("11.22"),
            CaseExplorerPage()
        ]

        for i, (name, page) in enumerate(zip(PAGES, self.pages)):
            button = QPushButton(name)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)

            self.group.addButton(button, i)
            segment_layout.addWidget(button)

            self.stack.addWidget(page)
            self.nav_buttons.append(button)

        self.group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_buttons[0].setChecked(True)

        nav_layout.addWidget(segment)
        nav_layout.addStretch(1)

        outer.addWidget(navbar)
        outer.addWidget(self.stack, 1)

        # FOOTER

        footer = QFrame()
        footer.setObjectName("footer")

        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(32, 6, 32, 6)

        self.foot_path = label("No file selected", "muted")
        self.foot_shape = label("", "muted")

        footer_layout.addWidget(self.foot_path, 1)
        footer_layout.addWidget(self.foot_shape)

        outer.addWidget(footer)

    # PUBLIC CONTRACT

    def set_event_data(self, df, path=None):
        self.event_df = df

        if path is not None:
            self.dataset_path = path

        for page in self.pages:
            page.set_event_data(df)

        if df is None:
            self._set_status("No dataset loaded", None)
            self.foot_shape.setText("")

        else:
            self._set_status(
                f"Dataset loaded · {len(df):,} events",
                "ok"
            )

            self.foot_shape.setText(
                f"event_df  {len(df):,} × {df.shape[1]}"
            )

        self.foot_path.setText(
            self.dataset_path or "No file selected"
        )

    def show_error(self, message):
        self._set_status(message, "err")

    # INTERNALS

    def _set_status(self, text, state):
        color = {
            "ok": C["ok"],
            "err": C["err"],
            None: C["olive"],
            "busy": C["brass"]
        }[state]

        self.status.setText(
            f'<span style="color:{color}">●</span>&nbsp;&nbsp;'
            f'<span style="color:{C["text2"]}">{text}</span>'
        )

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import XES event log",
            self.dataset_path or "",
            "XES logs (*.xes *.xes.gz);;All files (*)"
        )

        if path:
            self.dataset_path = path
            self.foot_path.setText(path)
            self._set_status("Loading dataset…", "busy")
            self.dataset_requested.emit(path)


def _demo_df(n=300):
    random.seed(1)

    activities = [
        "A_Create Application",
        "A_Submitted",
        "W_Handle leads",
        "A_Concept",
        "W_Complete application",
        "A_Accepted",
        "O_Create Offer",
        "O_Sent (mail and online)",
        "W_Call after offers",
        "A_Pending"
    ]

    rows = []

    for case_number in range(n):
        time = (
            pd.Timestamp("2016-01-01")
            + pd.Timedelta(hours=random.randint(0, 8000))
        )

        selected_activities = activities[
            :random.randint(4, len(activities))
        ]

        for activity in selected_activities:
            time += pd.Timedelta(
                minutes=random.randint(1, 3000)
            )

            rows.append((
                f"Application_{1000 + case_number}",
                activity,
                time,
                f"User_{random.randint(1, 40)}",
                random.choice(["start", "complete"])
            ))

    return pd.DataFrame(
        rows,
        columns=[
            "case:concept:name",
            "concept:name",
            "time:timestamp",
            "org:resource",
            "lifecycle:transition"
        ]
    )


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)

    window = MainWindow()

    if "--demo" in sys.argv:
        window.set_event_data(
            _demo_df(),
            path="(synthetic demo data)"
        )

    else:
        def fallback_loader(path):
            try:
                import pm4py

                QApplication.setOverrideCursor(Qt.WaitCursor)

                df = pm4py.read_xes(path)

                window.set_event_data(
                    pd.DataFrame(df),
                    path=path
                )

            except ImportError:
                window.show_error(
                    "No loader connected (install pm4py or connect dataset_requested)"
                )

            except Exception as error:
                window.show_error(f"Load failed: {error}")

            finally:
                while QApplication.overrideCursor():
                    QApplication.restoreOverrideCursor()

        window.dataset_requested.connect(fallback_loader)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
