"""Utilitas ekspor hasil analisis, daftar case, dan timeline ke file CSV."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core.data_contract import CASE_ID_ATTRIBUTE, validate_event_dataframe
from utils.case_timeline import get_case_events


def _validate_output_path(file_path: str | Path) -> Path:
    """Validasi path tujuan CSV dan pastikan folder induk tersedia."""
    if not isinstance(file_path, (str, Path)) or not str(file_path).strip():
        raise ValueError("Path tujuan ekspor CSV tidak boleh kosong.")

    path = Path(file_path).expanduser()
    if path.exists() and path.is_dir():
        raise ValueError(f"Path tujuan merupakan direktori, bukan file: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_csv_value(value: Any) -> str:
    """Konversi nilai Python/Pandas menjadi teks yang aman untuk sel CSV."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _format_evidence_summary(events: Sequence[Mapping[str, Any]]) -> str:
    """Ringkas daftar event evidence menjadi string yang mudah dibaca di CSV."""
    parts: list[str] = []
    for event in events:
        activity = event.get("activity", "?")
        ts = event.get("timestamp") or "NaT"
        idx = event.get("event_index", event.get("index", "?"))
        extras: list[str] = []
        if event.get("lifecycle:transition"):
            extras.append(str(event["lifecycle:transition"]))
        if event.get("org:resource"):
            extras.append(f"res={event['org:resource']}")
        extra_str = f" [{', '.join(extras)}]" if extras else ""
        parts.append(f"#{idx} {activity} ({ts}){extra_str}")
    return " -> ".join(parts)


def sanitize_filename_component(text: str) -> str:
    """Bersihkan teks (mis. Case ID) agar aman dipakai sebagai nama file."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text).strip())
    return cleaned.strip("._") or "export"


def export_rows_to_csv(
    rows: Sequence[Mapping[str, Any]],
    file_path: str | Path,
    *,
    fieldnames: Sequence[str] | None = None,
    encoding: str = "utf-8",
) -> Path:
    """Ekspor kumpulan baris dict ke file CSV secara deterministik.

    Args:
        rows: Daftar mapping kolom -> nilai.
        file_path: Path file CSV tujuan.
        fieldnames: Urutan nama kolom eksplisit. Jika ``None``, diambil dari
            urutan kemunculan key pada ``rows``.
        encoding: Encoding teks keluaran (default ``utf-8``).

    Returns:
        ``Path`` file CSV yang berhasil ditulis.
    """
    path = _validate_output_path(file_path)

    if fieldnames is not None:
        resolved_fields = [str(name) for name in fieldnames]
    else:
        resolved_fields = []
        seen: set[str] = set()
        for row in rows:
            for key in row.keys():
                key_str = str(key)
                if key_str not in seen:
                    seen.add(key_str)
                    resolved_fields.append(key_str)

    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=resolved_fields,
            extrasaction="ignore",
        )
        if resolved_fields:
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        field: _serialize_csv_value(row.get(field))
                        for field in resolved_fields
                    }
                )

    return path


def export_dataframe_to_csv(
    df: pd.DataFrame,
    file_path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Ekspor Pandas DataFrame ke file CSV tanpa memodifikasi DataFrame asal."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df harus berupa Pandas DataFrame.")

    path = _validate_output_path(file_path)
    df.to_csv(path, index=False, encoding=encoding)
    return path


def export_case_timeline_to_csv(
    event_df: pd.DataFrame,
    case_id: str,
    file_path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Ekspor timeline terurut untuk satu case tertentu ke CSV.

    Raises:
        ValueError: Jika ``case_id`` tidak ditemukan pada ``event_df`` atau
            path keluaran tidak valid.
    """
    validate_event_dataframe(event_df, allow_empty=True)
    case_events = get_case_events(event_df, case_id)
    if case_events.empty:
        raise ValueError(
            f"Case '{case_id}' tidak ditemukan pada DataFrame event."
        )

    export_df = case_events.copy()
    export_df.insert(0, "event_step", range(1, len(export_df) + 1))
    return export_dataframe_to_csv(export_df, file_path, encoding=encoding)


def _flatten_analysis_result(result: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Ubah dict hasil analisis standar (11.7 / 11.15 / 11.18 / 11.22) ke baris datar."""
    exercise = str(result.get("exercise", ""))
    details = result.get("details")

    flat_rows: list[dict[str, Any]] = []

    if isinstance(details, list) and details:
        first = details[0]
        # Bentuk Exercise 11.7: details berisi daftar subsoal dengan key 'case_evidence'.
        if isinstance(first, Mapping) and "case_evidence" in first:
            for sub in details:
                code = str(sub.get("code", ""))
                title = str(sub.get("title", ""))
                evidence_list = sub.get("case_evidence") or []
                if not evidence_list:
                    flat_rows.append(
                        {
                            "exercise": exercise,
                            "subquestion": code,
                            "title": title,
                            "case_id": "",
                            "cycle_time_days": "",
                            "matched_count": 0,
                            "n_events": 0,
                            "evidence_summary": "",
                        }
                    )
                    continue
                for row in evidence_list:
                    events = row.get("evidence_events") or []
                    flat_rows.append(
                        {
                            "exercise": exercise,
                            "subquestion": code,
                            "title": title,
                            "case_id": row.get("case_id", ""),
                            "cycle_time_days": row.get("cycle_time_days", ""),
                            "matched_count": row.get("matched_count", ""),
                            "n_events": row.get("n_events", ""),
                            "last_activity": row.get("last_activity", ""),
                            "first_timestamp": row.get("first_timestamp", ""),
                            "last_timestamp": row.get("last_timestamp", ""),
                            "evidence_summary": _format_evidence_summary(events),
                        }
                    )
        else:
            # Bentuk Exercise 11.15, 11.18, 11.22: details berisi daftar dict per case.
            for item in details:
                if not isinstance(item, Mapping):
                    continue
                flat: dict[str, Any] = {"exercise": exercise}
                for key, val in item.items():
                    if key == "evidence_events" and isinstance(val, list):
                        flat["evidence_summary"] = _format_evidence_summary(val)
                    elif key == "timeline_excerpt" and isinstance(val, list):
                        flat["timeline_excerpt"] = _format_evidence_summary(val)
                    else:
                        flat[str(key)] = val
                flat_rows.append(flat)
    elif isinstance(result.get("case_ids"), list) and result["case_ids"]:
        for cid in result["case_ids"]:
            flat_rows.append({"exercise": exercise, "case_id": str(cid)})

    if flat_rows:
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in flat_rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
        return flat_rows, fieldnames

    # Hasil kosong: tetap tulis header standar yang informatif.
    return [], ["exercise", "case_id", "evidence_summary"]


def export_analysis_result_to_csv(
    result: Mapping[str, Any],
    file_path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Ekspor dict hasil analisis sesuai kontrak ``TEAM_BASELINE.md`` ke CSV.

    Mendukung hasil dari Exercise 11.7, 11.15, 11.18, maupun 11.22, termasuk
    kondisi hasil kosong (0 case cocok).
    """
    if not isinstance(result, Mapping):
        raise TypeError("result harus berupa mapping/dict hasil analisis.")

    rows, fieldnames = _flatten_analysis_result(result)
    return export_rows_to_csv(
        rows,
        file_path,
        fieldnames=fieldnames,
        encoding=encoding,
    )


def export_case_summaries_to_csv(
    summaries: Sequence[Mapping[str, Any]],
    file_path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Ekspor daftar ringkasan case (dari Case Explorer) ke CSV."""
    default_fields = [
        "case_id",
        "event_count",
        "unique_activities",
        "start_time",
        "end_time",
        "duration_seconds",
        "duration_days",
        "duration_display",
        "first_activity",
        "last_activity",
        "has_invalid_timestamps",
    ]
    return export_rows_to_csv(
        summaries,
        file_path,
        fieldnames=default_fields,
        encoding=encoding,
    )


__all__ = [
    "CASE_ID_ATTRIBUTE",
    "export_analysis_result_to_csv",
    "export_case_summaries_to_csv",
    "export_case_timeline_to_csv",
    "export_dataframe_to_csv",
    "export_rows_to_csv",
    "sanitize_filename_component",
]
