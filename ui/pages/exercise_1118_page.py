"""Halaman GUI PySide6 untuk Exercise 11.18.

Menyediakan ``Exercise1118Page(QWidget)`` untuk menampilkan case yang memiliki
minimal 2 event ``W_Assess Potential Fraud`` berstatus ``complete`` oleh
resource yang sama dalam satu case.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd
from PySide6.QtWidgets import QApplication, QTableWidgetItem, QWidget

from analysis.exercise_1118 import EXERCISE_1118_RULE, analyze_exercise_1118
from ui.pages.exercise_1115_page import BaseExercisePage


class Exercise1118Page(BaseExercisePage):
    """Halaman QWidget untuk menampilkan analisis Exercise 11.18.

    Mewarisi ``BaseExercisePage`` dengan sinyal integrasi ``case_selected(str)``
    dan ``result_ready(dict)`` agar dapat dihubungkan ke Case Explorer oleh
    modul utama.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Exercise 11.18",
            rule_description=EXERCISE_1118_RULE,
            analyzer_fn=analyze_exercise_1118,
            case_headers=["Case ID", "Resource", "Complete Count"],
            parent=parent,
        )

    def _populate_case_table(self, details: list[dict[str, Any]]) -> None:
        self.case_table.setRowCount(len(details))
        for row_idx, item in enumerate(details):
            self.case_table.setItem(
                row_idx, 0, QTableWidgetItem(str(item.get("case_id", "")))
            )
            self.case_table.setItem(
                row_idx, 1, QTableWidgetItem(str(item.get("resource", "")))
            )
            self.case_table.setItem(
                row_idx,
                2,
                QTableWidgetItem(str(item.get("complete_count_by_resource", 0))),
            )


def _build_demo_dataframe() -> pd.DataFrame:
    csv_path = os.environ.get("BPIC17_CSV_PATH", "")
    if csv_path and os.path.isfile(csv_path):
        return pd.read_csv(csv_path)

    return pd.DataFrame(
        [
            {
                "case:concept:name": "Demo_Case_01",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T10:00:00+00:00",
                "org:resource": "User_A",
                "EventID": "E_101",
            },
            {
                "case:concept:name": "Demo_Case_01",
                "concept:name": "W_Assess Potential Fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-01T11:00:00+00:00",
                "org:resource": "User_A",
                "EventID": "E_102",
            },
            {
                "case:concept:name": "Demo_Case_02",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-02T09:00:00+00:00",
                "org:resource": "User_1",
                "EventID": "E_201",
            },
            {
                "case:concept:name": "Demo_Case_02",
                "concept:name": "W_Assess potential fraud",
                "lifecycle:transition": "complete",
                "time:timestamp": "2016-01-02T09:30:00+00:00",
                "org:resource": "User_2",
                "EventID": "E_202",
            },
        ]
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = Exercise1118Page()
    page.setWindowTitle("Demo Mandiri - Exercise 11.18")
    page.resize(960, 560)
    page.set_event_data(_build_demo_dataframe())
    page.show()
    sys.exit(app.exec())
