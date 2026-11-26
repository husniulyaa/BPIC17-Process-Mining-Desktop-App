"""Fluxicon Disco-inspired Same-Officer Fraud Rework page (F05).

Wraps ``analysis.exercise_1118.analyze_exercise_1118`` without modifying the
underlying analysis module.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pandas as pd
from PySide6.QtWidgets import QApplication, QWidget

from analysis.exercise_1118 import analyze_exercise_1118
from ui.pages.exercise_1115_page import BaseExercisePage


class Exercise1118Page(BaseExercisePage):
    """Same-Officer Fraud Rework page (>= 2 completed fraud checks by same resource)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Same-Officer Fraud Rework",
            rule_description=(
                "Identifies unique cases where the exact same resource ('org:resource') "
                "completed 'W_Assess Potential Fraud' at least twice within the same case. "
                "Missing/blank resources are never treated as identical."
            ),
            analyzer_fn=analyze_exercise_1118,
            case_headers=["Case ID", "Repeating Officer", "Completions by Officer"],
            metric_key="complete_count_by_resource",
            export_slug="same_officer_fraud_rework",
            parent=parent,
        )

    def _build_case_rows(
        self,
        details: list[dict[str, Any]],
    ) -> list[tuple[list[Any], dict[str, Any]]]:
        return [
            (
                [
                    str(item.get("case_id", "")),
                    str(item.get("resource", "")),
                    int(item.get("complete_count_by_resource", 0)),
                ],
                item,
            )
            for item in details
        ]


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
        ]
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    page = Exercise1118Page()
    page.resize(1040, 620)
    page.show()
    page.set_event_data(_build_demo_dataframe())
    sys.exit(app.exec())
