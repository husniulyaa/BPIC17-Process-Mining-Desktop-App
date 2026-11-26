"""Fluxicon Disco-inspired Global Statistics & Dataset Overview page (F02).

Optimized for 1M+ event logs:
- Replaces ``DataFrame.iterrows()`` and Python per-group lambdas with fast
  NumPy/Pandas array extraction and cooperative GIL yields.
- Schedules background work through ``GLOBAL_TASK_SCHEDULER`` so multiple tabs
  never contend for CPU/RAM simultaneously.
- Retains ``calculate_case_durations(event_df)`` at module level for full
  compatibility with ``tests/test_overview_page.py``.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)
from ui.disco_widgets import (
    DiscoBarDelegate,
    DiscoDarkChart,
    DiscoKpiPanel,
    DiscoSidebarList,
    make_disco_search,
    style_disco_table,
)
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from utils.case_timeline import format_human_duration
from utils.exporter import export_rows_to_csv


def calculate_case_durations(event_df: pd.DataFrame) -> pd.DataFrame:
    """Return one start, end, and cycle-time row per case.

    A case with any invalid timestamp has NaT for its time bounds
    and cycle time, because its complete duration cannot be determined.
    """
    validate_event_dataframe(event_df, allow_empty=True)

    ts_col = event_df[TIMESTAMP_ATTRIBUTE]
    if isinstance(ts_col.dtype, pd.DatetimeTZDtype) and str(ts_col.dtype.tz) == "UTC":
        timestamps = ts_col
    else:
        try:
            timestamps = pd.to_datetime(
                ts_col,
                errors="coerce",
                utc=True,
                format="mixed",
            )
        except (TypeError, ValueError):
            timestamps = pd.to_datetime(
                ts_col,
                errors="coerce",
                utc=True,
            )

    case_events = pd.DataFrame(
        {
            CASE_ID_ATTRIBUTE: event_df[CASE_ID_ATTRIBUTE].reset_index(drop=True),
            TIMESTAMP_ATTRIBUTE: timestamps.reset_index(drop=True),
        }
    )

    grouped = case_events.groupby(
        CASE_ID_ATTRIBUTE,
        sort=True,
        dropna=True,
    )

    durations = grouped[TIMESTAMP_ATTRIBUTE].agg(
        start_time="min",
        end_time="max",
        valid_cnt="count",
        total_cnt="size",
    )

    invalid_cases = durations["valid_cnt"] < durations["total_cnt"]
    durations.loc[invalid_cases, ["start_time", "end_time"]] = pd.NaT
    durations = durations.drop(columns=["valid_cnt", "total_cnt"])
    durations["cycle_time"] = durations["end_time"] - durations["start_time"]
    return durations.reset_index()


def _compute_statistics_bundle(event_df: pd.DataFrame) -> dict[str, Any]:
    """Compute global statistics, histograms, and view tables without iterrows()."""
    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return {"empty": True}

    ts_col = event_df[TIMESTAMP_ATTRIBUTE]
    if isinstance(ts_col.dtype, pd.DatetimeTZDtype) and str(ts_col.dtype.tz) == "UTC":
        ts = ts_col
    else:
        try:
            ts = pd.to_datetime(ts_col, errors="coerce", utc=True, format="mixed")
        except (TypeError, ValueError):
            ts = pd.to_datetime(ts_col, errors="coerce", utc=True)

    valid_ts = ts.dropna()
    start_str = valid_ts.min().strftime("%d.%m.%Y %H:%M:%S") if not valid_ts.empty else "—"
    end_str = valid_ts.max().strftime("%d.%m.%Y %H:%M:%S") if not valid_ts.empty else "—"

    res_col = OPTIONAL_ATTRIBUTES[1]
    lc_col = OPTIONAL_ATTRIBUTES[0]
    has_res = res_col in event_df.columns
    has_lc = lc_col in event_df.columns

    total_events = len(event_df)
    cids = pd.Categorical(event_df[CASE_ID_ATTRIBUTE].astype(str))
    acts = pd.Categorical(
        event_df[ACTIVITY_ATTRIBUTE].where(
            event_df[ACTIVITY_ATTRIBUTE].notna(), "(missing)"
        ).astype(str)
    )
    total_cases = int(len(cids.categories))
    total_activities = int(len(acts.categories))
    total_resources = int(event_df[res_col].dropna().nunique()) if has_res else 0

    time.sleep(0)

    work = pd.DataFrame({"cid": cids, "act": acts, "ts": ts.reset_index(drop=True)})
    grp = work.groupby("cid", sort=True, observed=True)
    case_agg = grp.agg(
        events=("act", "size"),
        started=("ts", "min"),
        finished=("ts", "max"),
        valid_ts=("ts", "count"),
    )

    time.sleep(0)

    has_invalid = (case_agg["valid_ts"] < case_agg["events"]).to_numpy()
    dur_sec_series = (case_agg["finished"] - case_agg["started"]).dt.total_seconds()
    dur_sec_series = dur_sec_series.mask(has_invalid)

    valid_dur = dur_sec_series.dropna()
    median_dur_str = (
        f"{float(valid_dur.median()) / 86400.0:.1f} d" if not valid_dur.empty else "—"
    )
    mean_dur_str = (
        f"{float(valid_dur.mean()) / 86400.0:.1f} d" if not valid_dur.empty else "—"
    )

    # Vectorized timestamp formatting + fast zip loop (no iterrows!)
    started_strs = case_agg["started"].dt.strftime("%d.%m.%Y %H:%M:%S").fillna("—").tolist()
    finished_strs = case_agg["finished"].dt.strftime("%d.%m.%Y %H:%M:%S").fillna("—").tolist()
    cid_list = case_agg.index.astype(str).tolist()
    ev_arr = case_agg["events"].to_numpy()
    dur_arr = dur_sec_series.to_numpy()

    case_rows: list[dict[str, Any]] = []
    for i, (cid, ev_cnt, inv, s_txt, f_txt, d_val) in enumerate(
        zip(cid_list, ev_arr, has_invalid, started_strs, finished_strs, dur_arr)
    ):
        if i % 5000 == 0 and i > 0:
            time.sleep(0)
        d_s = None if inv or np.isnan(d_val) else float(d_val)
        case_rows.append(
            {
                "col0": cid,
                "col1_str": f"{int(ev_cnt):,}",
                "col1_num": float(ev_cnt),
                "col2": "—" if inv else s_txt,
                "col3": "—" if inv else f_txt,
                "col4_str": format_human_duration(d_s),
                "col4_num": float(d_s or 0.0),
            }
        )

    # Activity classes table
    act_counts = work.groupby("act", observed=True).agg(
        freq=("act", "size"),
        cases=("cid", "nunique"),
    ).sort_values("freq", ascending=False)
    activity_rows = [
        {
            "col0": str(act),
            "col1_str": f"{int(freq):,}",
            "col1_num": float(freq),
            "col2": f"{int(c_cnt):,}",
            "col3": f"{(freq / max(1, total_events) * 100.0):.2f}%",
            "col4_str": f"{(c_cnt / max(1, total_cases) * 100.0):.2f}%",
            "col4_num": float(c_cnt),
        }
        for act, freq, c_cnt in zip(
            act_counts.index.astype(str),
            act_counts["freq"].to_numpy(),
            act_counts["cases"].to_numpy(),
        )
    ]

    # Resource classes table
    resource_rows: list[dict[str, Any]] = []
    if has_res:
        res_cat = pd.Categorical(
            event_df[res_col].where(event_df[res_col].notna(), "(unassigned)").astype(str)
        )
        res_df = pd.DataFrame({"res": res_cat, "cid": cids})
        res_agg = res_df.groupby("res", observed=True).agg(
            freq=("res", "size"),
            cases=("cid", "nunique"),
        ).sort_values("freq", ascending=False)
        resource_rows = [
            {
                "col0": str(res_name),
                "col1_str": f"{int(freq):,}",
                "col1_num": float(freq),
                "col2": f"{int(c_cnt):,}",
                "col3": f"{(freq / max(1, total_events) * 100.0):.2f}%",
                "col4_str": f"{(c_cnt / max(1, total_cases) * 100.0):.2f}%",
                "col4_num": float(c_cnt),
            }
            for res_name, freq, c_cnt in zip(
                res_agg.index.astype(str),
                res_agg["freq"].to_numpy(),
                res_agg["cases"].to_numpy(),
            )
        ]

    # Lifecycle classes table
    lifecycle_rows: list[dict[str, Any]] = []
    if has_lc:
        lc_cat = pd.Categorical(
            event_df[lc_col].where(event_df[lc_col].notna(), "(unspecified)").astype(str)
        )
        lc_df = pd.DataFrame({"lc": lc_cat, "cid": cids})
        lc_agg = lc_df.groupby("lc", observed=True).agg(
            freq=("lc", "size"),
            cases=("cid", "nunique"),
        ).sort_values("freq", ascending=False)
        lifecycle_rows = [
            {
                "col0": str(lc_name),
                "col1_str": f"{int(freq):,}",
                "col1_num": float(freq),
                "col2": f"{int(c_cnt):,}",
                "col3": f"{(freq / max(1, total_events) * 100.0):.2f}%",
                "col4_str": f"{(c_cnt / max(1, total_cases) * 100.0):.2f}%",
                "col4_num": float(c_cnt),
            }
            for lc_name, freq, c_cnt in zip(
                lc_agg.index.astype(str),
                lc_agg["freq"].to_numpy(),
                lc_agg["cases"].to_numpy(),
            )
        ]

    # Chart series
    charts: dict[str, dict[str, Any]] = {}
    if not valid_ts.empty and valid_ts.max() > valid_ts.min():
        bins = pd.cut(valid_ts, bins=48)
        counts = bins.value_counts().sort_index()
        charts["events_over_time"] = {
            "values": [float(v) for v in counts.values],
            "labels": [
                valid_ts.min().strftime("%d.%m.%Y"),
                valid_ts.max().strftime("%d.%m.%Y"),
            ],
            "kind": "area",
            "x_caption": "Timeline",
            "y_caption": "Events",
        }
    else:
        charts["events_over_time"] = {
            "values": [float(total_events)] if total_events else [],
            "labels": [start_str, end_str],
            "kind": "bars",
            "x_caption": "Timeline",
            "y_caption": "Events",
        }

    ev_per_case = case_agg["events"]
    epc_bins = pd.cut(ev_per_case, bins=min(36, max(1, int(ev_per_case.nunique()))))
    epc_counts = epc_bins.value_counts().sort_index()
    charts["events_per_case"] = {
        "values": [float(v) for v in epc_counts.values],
        "labels": [f"{int(ev_per_case.min())} ev", f"{int(ev_per_case.max())} ev"],
        "kind": "bars",
        "x_caption": "Events per case",
        "y_caption": "Number of cases",
    }

    if not valid_dur.empty:
        days_series = valid_dur / 86400.0
        dur_bins = pd.cut(days_series, bins=min(40, max(1, len(days_series))))
        dur_counts = dur_bins.value_counts().sort_index()
        charts["case_duration"] = {
            "values": [float(v) for v in dur_counts.values],
            "labels": [f"{days_series.min():.1f} d", f"{days_series.max():.1f} d"],
            "kind": "bars",
            "x_caption": "Case duration (days)",
            "y_caption": "Number of cases",
        }
    else:
        charts["case_duration"] = {
            "values": [],
            "labels": [],
            "kind": "bars",
            "x_caption": "Case duration",
            "y_caption": "Number of cases",
        }

    charts["activity_freq"] = {
        "values": [float(r["col1_num"]) for r in activity_rows[:30]],
        "labels": [
            activity_rows[0]["col0"] if activity_rows else "",
            activity_rows[min(len(activity_rows) - 1, 29)]["col0"] if activity_rows else "",
        ],
        "kind": "bars",
        "x_caption": "Activities (ranked by frequency)",
        "y_caption": "Events",
    }

    return {
        "empty": False,
        "kpis": {
            "events": f"{total_events:,}",
            "cases": f"{total_cases:,}",
            "activities": f"{total_activities:,}",
            "resources": f"{total_resources:,}" if has_res else "N/A",
            "median_dur": median_dur_str,
            "mean_dur": mean_dur_str,
            "start": start_str,
            "end": end_str,
        },
        "case_rows": case_rows,
        "activity_rows": activity_rows,
        "resource_rows": resource_rows,
        "lifecycle_rows": lifecycle_rows,
        "charts": charts,
    }


class _StatsTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._headers: tuple[str, ...] = (
            "Case ID",
            "Events",
            "Started",
            "Finished",
            "Duration",
        )
        self._rows: list[dict[str, Any]] = []
        self._max_col1 = 1.0
        self._max_col4 = 1.0

    def set_table(self, headers: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._headers = headers
        self._rows = list(rows)
        self._max_col1 = max((float(r.get("col1_num") or 0.0) for r in rows), default=1.0) or 1.0
        self._max_col4 = max((float(r.get("col4_num") or 0.0) for r in rows), default=1.0) or 1.0
        self.endResetModel()

    def max_for_column(self, col: int) -> float:
        if col == 1:
            return self._max_col1
        if col == 4:
            return self._max_col4
        return 0.0

    def rows(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def headers(self) -> tuple[str, ...]:
        return self._headers

    def col0_at(self, row: int) -> str:
        return str(self._rows[row]["col0"]) if 0 <= row < len(self._rows) else ""

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return row["col0"]
            if col == 1:
                return row["col1_str"]
            if col == 2:
                return row["col2"]
            if col == 3:
                return row["col3"]
            if col == 4:
                return row["col4_str"]

        if role == Qt.ItemDataRole.UserRole:
            if col == 0:
                return row["col0"]
            if col == 1:
                return float(row.get("col1_num") or 0.0)
            if col == 2:
                return row["col2"]
            if col == 3:
                return row["col3"]
            if col == 4:
                return float(row.get("col4_num") or 0.0)

        if role == Qt.ItemDataRole.TextAlignmentRole and col in (1, 4):
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return None


class OverviewPage(QWidget):
    """Fluxicon Disco-inspired Global Statistics & Overview tab."""

    open_case_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Global Statistics")
        self.event_df: pd.DataFrame | None = None
        self._bundle: dict[str, Any] | None = None
        self._dirty = False
        self._current_view_key = "overview"
        self._current_chart_key = "events_over_time"

        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = DiscoSidebarList("Statistics views", self)
        self.sidebar.setFixedWidth(215)
        self.sidebar.set_items(
            [
                ("overview", "Overview", "Global statistics"),
                ("activity", "Activity", "Activity classes"),
                ("resource", "Resource", "Resource classes"),
                ("lifecycle", "Lifecycle transition", "Transition classes"),
            ]
        )
        self.sidebar.item_selected.connect(self._on_sidebar_changed)
        root.addWidget(self.sidebar)

        right = QWidget()
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(18, 14, 18, 12)
        r_layout.setSpacing(10)

        hdr = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.lbl_view_title = QLabel("Overview")
        self.lbl_view_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #22262A;")
        self.lbl_view_sub = QLabel("Global statistics")
        self.lbl_view_sub.setStyleSheet("color: #6C737B; font-size: 11px;")
        title_box.addWidget(self.lbl_view_title)
        title_box.addWidget(self.lbl_view_sub)
        hdr.addLayout(title_box)

        hdr.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(140)
        self.progress.setTextVisible(False)
        self.progress.hide()
        hdr.addWidget(self.progress)

        self.txt_search = make_disco_search("Filter table...")
        self.txt_search.setFixedWidth(200)
        self.txt_search.textChanged.connect(self._apply_search)
        hdr.addWidget(self.txt_search)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setObjectName("toolbarBtn")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(lambda: self.export_current_table())
        hdr.addWidget(self.btn_export)

        r_layout.addLayout(hdr)

        top_card = QFrame()
        top_card.setObjectName("discoWhitePanel")
        top_layout = QHBoxLayout(top_card)
        top_layout.setContentsMargins(12, 12, 14, 12)
        top_layout.setSpacing(14)

        pills_col = QVBoxLayout()
        pills_col.setSpacing(5)
        self._pill_group = QButtonGroup(self)
        self._pill_group.setExclusive(True)
        chart_specs = [
            ("events_over_time", "Events over time"),
            ("events_per_case", "Events per case"),
            ("case_duration", "Case duration"),
            ("activity_freq", "Activity frequency"),
        ]
        for idx, (ckey, clabel) in enumerate(chart_specs):
            btn = QPushButton(clabel)
            btn.setObjectName("metricPill")
            btn.setCheckable(True)
            btn.setFixedWidth(138)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if idx == 0:
                btn.setChecked(True)
            self._pill_group.addButton(btn, idx)
            btn.clicked.connect(lambda _c=False, k=ckey: self._set_chart(k))
            pills_col.addWidget(btn)
        pills_col.addStretch(1)
        top_layout.addLayout(pills_col)

        self.chart = DiscoDarkChart(top_card)
        self.chart.setMinimumHeight(180)
        top_layout.addWidget(self.chart, 1)

        self.kpi_panel = DiscoKpiPanel(
            [
                ("events", "Events"),
                ("cases", "Cases"),
                ("activities", "Activities"),
                ("resources", "Resources"),
                ("median_dur", "Median case duration"),
                ("mean_dur", "Mean case duration"),
                ("start", "Start"),
                ("end", "End"),
            ],
            top_card,
        )
        top_layout.addWidget(self.kpi_panel)

        r_layout.addWidget(top_card)

        tbl_bar = QHBoxLayout()
        self.lbl_table_caption = QLabel("Cases")
        self.lbl_table_caption.setStyleSheet("font-weight: 700; color: #3A4046;")
        tbl_bar.addWidget(self.lbl_table_caption)
        tbl_bar.addStretch(1)

        self.btn_inspect_case = QPushButton("Open Selected Case")
        self.btn_inspect_case.setObjectName("primaryActionBtn")
        self.btn_inspect_case.setEnabled(False)
        self.btn_inspect_case.clicked.connect(self._open_selected_case)
        tbl_bar.addWidget(self.btn_inspect_case)
        r_layout.addLayout(tbl_bar)

        self.model = _StatsTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterKeyColumn(0)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.table = style_disco_table(QTableView())
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        bar_delegate = DiscoBarDelegate(self.model.max_for_column, parent=self.table)
        self.table.setItemDelegateForColumn(1, bar_delegate)
        self.table.setItemDelegateForColumn(4, bar_delegate)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda _idx: self._open_selected_case())
        r_layout.addWidget(self.table, 1)

        root.addWidget(right, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        if event_df is not None:
            validate_event_dataframe(event_df, allow_empty=True)

        self.event_df = event_df
        self._bundle = None
        self._clear_ui()

        if event_df is None or event_df.empty:
            self._dirty = False
            self.progress.hide()
            return

        self._dirty = True
        if self.isVisible():
            self.refresh_statistics()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty and self.event_df is not None and not self.event_df.empty:
            self.refresh_statistics()

    def refresh_statistics(self) -> None:
        if self.event_df is None or self.event_df.empty:
            return
        df_ref = self.event_df
        self._dirty = False
        self.progress.show()
        GLOBAL_TASK_SCHEDULER.submit(
            "statistics_overview",
            lambda: _compute_statistics_bundle(df_ref),
            self._on_completed,
            self._on_failed,
            high_priority=True,
        )

    def export_current_table(self, file_path: str | Path | None = None) -> Path | None:
        rows = self.model.rows()
        if not rows:
            return None

        target = file_path
        if target is None:
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Export Statistics Table to CSV",
                f"statistics_{self._current_view_key}.csv",
                "CSV Files (*.csv);;All Files (*)",
            )
            if not selected:
                return None
            target = selected

        headers = self.model.headers()
        flat_rows = [
            {
                headers[0]: r["col0"],
                headers[1]: r["col1_str"],
                headers[2]: r["col2"],
                headers[3]: r["col3"],
                headers[4]: r["col4_str"],
            }
            for r in rows
        ]
        try:
            return export_rows_to_csv(flat_rows, target, fieldnames=headers)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "CSV Export Failed", str(exc))
            return None

    # ------------------------------------------------------------ internals
    def _on_completed(self, bundle: dict[str, Any]) -> None:
        self.progress.hide()
        if bundle.get("empty"):
            return
        self._bundle = bundle
        for key, val in bundle["kpis"].items():
            self.kpi_panel.set_value(key, val)
        self.btn_export.setEnabled(True)
        self._apply_view(self._current_view_key)
        self._set_chart(self._current_chart_key)

    def _on_failed(self, msg: str) -> None:
        self.progress.hide()
        self.chart.clear_chart(f"Failed to compute statistics: {msg}")

    def _on_sidebar_changed(self, key: str) -> None:
        self._current_view_key = key
        self._apply_view(key)

    def _apply_view(self, key: str) -> None:
        titles = {
            "overview": ("Overview", "Global case statistics & cycle durations"),
            "activity": ("Activity Classes", "Frequency and case coverage per activity"),
            "resource": ("Resource Classes", "Event workload and case involvement per resource"),
            "lifecycle": ("Lifecycle Transitions", "Distribution across XES lifecycle states"),
        }
        t, sub = titles.get(key, ("Overview", "Global statistics"))
        self.lbl_view_title.setText(t)
        self.lbl_view_sub.setText(sub)

        if not self._bundle or self._bundle.get("empty"):
            return

        if key == "overview":
            headers = ("Case ID", "Events", "Started", "Finished", "Duration")
            rows = self._bundle["case_rows"]
            self.btn_inspect_case.show()
        elif key == "activity":
            headers = ("Activity", "Frequency", "Cases", "Event Share", "Case Coverage")
            rows = self._bundle["activity_rows"]
            self.btn_inspect_case.hide()
        elif key == "resource":
            headers = ("Resource", "Frequency", "Cases", "Event Share", "Case Coverage")
            rows = self._bundle["resource_rows"]
            self.btn_inspect_case.hide()
        else:
            headers = ("Lifecycle", "Frequency", "Cases", "Event Share", "Case Coverage")
            rows = self._bundle["lifecycle_rows"]
            self.btn_inspect_case.hide()

        self.model.set_table(headers, rows)
        self._update_table_caption()

    def _set_chart(self, chart_key: str) -> None:
        self._current_chart_key = chart_key
        if not self._bundle or self._bundle.get("empty"):
            return
        spec = self._bundle["charts"].get(chart_key)
        if spec:
            self.chart.set_series(
                spec["values"],
                spec["labels"],
                kind=spec["kind"],
                x_caption=spec["x_caption"],
                y_caption=spec["y_caption"],
            )

    def _apply_search(self, text: str) -> None:
        self.proxy.setFilterFixedString(text.strip())
        self._update_table_caption()

    def _update_table_caption(self) -> None:
        total = self.model.rowCount()
        shown = self.proxy.rowCount()
        noun = "cases" if self._current_view_key == "overview" else "classes"
        self.lbl_table_caption.setText(
            f"Showing {shown:,} of {total:,} {noun}" if total else "No records loaded"
        )

    def _on_selection_changed(self) -> None:
        has_sel = (
            self._current_view_key == "overview"
            and bool(self.table.selectionModel().selectedRows())
        )
        self.btn_inspect_case.setEnabled(has_sel)

    def _open_selected_case(self) -> None:
        if self._current_view_key != "overview":
            return
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return
        src_row = self.proxy.mapToSource(sel[0]).row()
        cid = self.model.col0_at(src_row)
        if cid:
            self.open_case_requested.emit(cid)

    def _clear_ui(self) -> None:
        self.kpi_panel.reset()
        self.chart.clear_chart()
        self.model.set_table(("Case ID", "Events", "Started", "Finished", "Duration"), [])
        self.btn_export.setEnabled(False)
        self.btn_inspect_case.setEnabled(False)
        self._update_table_caption()


__all__ = ["OverviewPage", "calculate_case_durations"]
