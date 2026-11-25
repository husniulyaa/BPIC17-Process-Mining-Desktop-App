"""Dataset overview page for a shared event DataFrame."""

from __future__ import annotations

from typing import Any

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)


def calculate_case_durations(event_df: pd.DataFrame) -> pd.DataFrame:
    """Return one start, end, and cycle-time row per case.

    A case with any invalid timestamp has NaT for its time bounds
    and cycle time, because its complete duration cannot be determined.
    """
    validate_event_dataframe(event_df, allow_empty=True)

    timestamps = pd.to_datetime(
        event_df[TIMESTAMP_ATTRIBUTE],
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
    )

    invalid_cases = grouped[TIMESTAMP_ATTRIBUTE].apply(
        lambda values: values.isna().any()
    )

    durations.loc[invalid_cases, ["start_time", "end_time"]] = pd.NaT

    durations["cycle_time"] = (
        durations["end_time"] - durations["start_time"]
    )

    return durations.reset_index()


class OverviewPage(QWidget):
    """Display event-log counts, time metrics, and per-case durations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dataset Overview")

        self._metrics: dict[str, QLabel] = {}
        self._frequency_table = self._create_table(("Activity", "Frequency"))
        self._case_table = self._create_table(
            ("Case ID", "Start time", "End time", "Cycle time")
        )

        root_layout = QVBoxLayout(self)
        title = QLabel("Dataset Overview")
        title.setObjectName("overviewTitle")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root_layout.addWidget(title)

        metric_layout = QGridLayout()
        metric_names = (
            "Total case",
            "Total event",
            "Unique activities",
            "Event time range",
            "Average cycle time",
        )
        for index, name in enumerate(metric_names):
            card = QWidget(self)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            name_label = QLabel(name)
            value_label = QLabel("—")
            value_label.setObjectName(f"metric_{index}")
            value_label.setWordWrap(True)
            value_label.setStyleSheet("font-size: 16px; font-weight: 600;")
            card_layout.addWidget(name_label)
            card_layout.addWidget(value_label)
            card.setObjectName("metricCard")
            card.setStyleSheet(
                "QWidget#metricCard { "
                "border: 1px solid #c8c8c8; border-radius: 5px; }"
            )
            metric_layout.addWidget(card, index // 3, index % 3)
            self._metrics[name] = value_label
        root_layout.addLayout(metric_layout)

        tables = QSplitter(Qt.Orientation.Horizontal, self)
        activity_panel = QWidget(tables)
        activity_layout = QVBoxLayout(activity_panel)
        activity_layout.addWidget(QLabel("Activity frequency"))
        activity_layout.addWidget(self._frequency_table)
        case_panel = QWidget(tables)
        case_layout = QVBoxLayout(case_panel)
        case_layout.addWidget(QLabel("Case durations"))
        case_layout.addWidget(self._case_table)
        tables.addWidget(activity_panel)
        tables.addWidget(case_panel)
        tables.setStretchFactor(0, 1)
        tables.setStretchFactor(1, 2)
        root_layout.addWidget(tables, 1)

    @staticmethod
    def _create_table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        table.verticalHeader().setVisible(False)
        return table

    @staticmethod
    def _format_timestamp(value: Any) -> str:
        if pd.isna(value):
            return "—"
        return value.strftime("%Y-%m-%d %H:%M:%S %Z")

    @staticmethod
    def _format_duration(value: Any) -> str:
        return "—" if pd.isna(value) else str(value)

    @staticmethod
    def _set_table_rows(
        table: QTableWidget,
        rows: list[tuple[str, ...]],
    ) -> None:
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                for column_index, value in enumerate(row):
                    item = QTableWidgetItem(value)
                    if column_index > 0:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignVCenter
                            | Qt.AlignmentFlag.AlignLeft
                        )
                    table.setItem(row_index, column_index, item)
        finally:
            table.setUpdatesEnabled(True)

    def set_event_data(self, event_df: pd.DataFrame) -> None:
        """Set the full event DataFrame and refresh all overview statistics."""
        validate_event_dataframe(event_df, allow_empty=True)

        if event_df.empty:
            for name in (
                "Total case",
                "Total event",
                "Unique activities",
            ):
                self._metrics[name].setText("0")
            self._metrics["Event time range"].setText("—")
            self._metrics["Average cycle time"].setText("—")
            self._set_table_rows(self._frequency_table, [])
            self._set_table_rows(self._case_table, [])
            return

        case_count = int(event_df[CASE_ID_ATTRIBUTE].nunique())
        event_count = len(event_df)
        activity_count = int(event_df[ACTIVITY_ATTRIBUTE].nunique())
        timestamps = pd.to_datetime(
            event_df[TIMESTAMP_ATTRIBUTE],
            errors="coerce",
            utc=True,
        )
        valid_timestamps = timestamps.dropna()
        if valid_timestamps.empty:
            time_range = "—"
        else:
            time_range = (
                f"{self._format_timestamp(valid_timestamps.min())} – "
                f"{self._format_timestamp(valid_timestamps.max())}"
            )

        case_durations = calculate_case_durations(event_df)
        valid_cycle_times = case_durations["cycle_time"].dropna()
        average_cycle_time = (
            self._format_duration(valid_cycle_times.mean())
            if not valid_cycle_times.empty
            else "—"
        )

        self._metrics["Total case"].setText(f"{case_count:,}")
        self._metrics["Total event"].setText(f"{event_count:,}")
        self._metrics["Unique activities"].setText(f"{activity_count:,}")
        self._metrics["Event time range"].setText(time_range)
        self._metrics["Average cycle time"].setText(average_cycle_time)

        activity_counts = event_df[ACTIVITY_ATTRIBUTE].value_counts(
            dropna=False,
            sort=True,
        )
        frequency_rows = [
            (
                "(missing)" if pd.isna(activity) else str(activity),
                f"{int(count):,}",
            )
            for activity, count in activity_counts.items()
        ]
        self._set_table_rows(self._frequency_table, frequency_rows)

        case_rows = [
            (
                (
                    "(missing)"
                    if pd.isna(row[CASE_ID_ATTRIBUTE])
                    else str(row[CASE_ID_ATTRIBUTE])
                ),
                self._format_timestamp(row["start_time"]),
                self._format_timestamp(row["end_time"]),
                self._format_duration(row["cycle_time"]),
            )
            for _, row in case_durations.iterrows()
        ]
        self._set_table_rows(self._case_table, case_rows)


__all__ = ["OverviewPage", "calculate_case_durations"]
