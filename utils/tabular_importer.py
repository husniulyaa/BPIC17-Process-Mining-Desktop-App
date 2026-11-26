"""Multi-format event data reader & Fluxicon Disco-style column mapper.

Supports loading raw tabular and semi-structured data files:
- XES / XES.GZ (via ``core.dataset_loader.load_xes``)
- CSV / TSV / TXT (configurable encoding, delimiter, quote handling)
- Excel workbooks: .xlsx, .xlsm, .xls (via openpyxl / pandas, with a pure-Python
  stdlib XML/ZIP fallback for .xlsx if openpyxl is not installed)
- XML / XMX / MXML (supports XES-like <trace>/<event>, MXML
  <ProcessInstance>/<AuditTrailEntry>, and flat <row>/<record> tables)
- JSON / JSONL / Parquet

Also provides heuristic role detection and non-destructive mapping to the
project's standard XES DataFrame contract:
- ``case:concept:name``
- ``concept:name``
- ``time:timestamp``
- ``org:resource`` (optional)
- ``lifecycle:transition`` (optional)
"""

from __future__ import annotations

import csv
import gzip
from pathlib import Path
import re
import shutil
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET
import zipfile

import pandas as pd

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    OPTIONAL_ATTRIBUTES,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)
from core.dataset_loader import load_xes

LIFECYCLE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[0]  # "lifecycle:transition"
RESOURCE_ATTRIBUTE = OPTIONAL_ATTRIBUTES[1]  # "org:resource"
START_TIMESTAMP_ATTRIBUTE = "time:start_timestamp"

ROLE_IGNORE = "ignore"
ROLE_CASE = "case"
ROLE_ACTIVITY = "activity"
ROLE_TIMESTAMP = "timestamp"
ROLE_RESOURCE = "resource"
ROLE_LIFECYCLE = "lifecycle"
ROLE_OTHER = "other"

VALID_ROLES = (
    ROLE_IGNORE,
    ROLE_CASE,
    ROLE_ACTIVITY,
    ROLE_TIMESTAMP,
    ROLE_RESOURCE,
    ROLE_LIFECYCLE,
    ROLE_OTHER,
)

SUPPORTED_FILE_FILTER = (
    "All Supported Data (*.xes *.xes.gz *.csv *.tsv *.txt *.xlsx *.xlsm *.xls "
    "*.xml *.xmx *.mxml *.json *.jsonl *.parquet);;"
    "XES Event Logs (*.xes *.xes.gz);;"
    "CSV / Delimited Text (*.csv *.tsv *.txt);;"
    "Excel Workbooks (*.xlsx *.xlsm *.xls);;"
    "XML / XMX / MXML Logs (*.xml *.xmx *.mxml);;"
    "JSON / Parquet (*.json *.jsonl *.parquet);;"
    "All Files (*)"
)

TIMESTAMP_FORMATS: dict[str, str | None] = {
    "Auto-detect": None,
    "DD/MM/YYYY HH:MM": "%d/%m/%Y %H:%M",
    "DD/MM/YYYY HH:MM:SS": "%d/%m/%Y %H:%M:%S",
    "YYYY-MM-DD HH:MM:SS": "%Y-%m-%d %H:%M:%S",
    "MM/DD/YYYY HH:MM": "%m/%d/%Y %H:%M",
    "DD.MM.YYYY HH:MM:SS": "%d.%m.%Y %H:%M:%S",
}


def is_xes_path(file_path: str | Path) -> bool:
    name = Path(file_path).name.lower()
    return name.endswith(".xes") or name.endswith(".xes.gz")


def is_csv_like_path(file_path: str | Path) -> bool:
    name = Path(file_path).name.lower()
    if name.endswith(".gz") and not name.endswith(".xes.gz"):
        name = name[:-3]
    return name.endswith((".csv", ".tsv", ".txt"))


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _read_xlsx_stdlib_fallback(path: Path) -> pd.DataFrame:
    """Fallback .xlsx reader using stdlib zipfile + ElementTree when openpyxl is absent."""
    ns_main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path, "r") as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root.findall(f"{ns_main}si"):
                texts = [t.text or "" for t in si.iter(f"{ns_main}t")]
                shared_strings.append("".join(texts))

        sheet_files = sorted(
            n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
        )
        if not sheet_files:
            raise ValueError(f"No worksheet found inside Excel file '{path.name}'.")

        sheet_root = ET.fromstring(zf.read(sheet_files[0]))
        rows_raw: list[dict[int, Any]] = []
        max_col = 0

        def col_letters_to_idx(cell_ref: str) -> int:
            letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
            idx = 0
            for ch in letters:
                idx = idx * 26 + (ord(ch) - ord("A") + 1)
            return max(0, idx - 1)

        for row_el in sheet_root.iter(f"{ns_main}row"):
            row_dict: dict[int, Any] = {}
            for c_el in row_el.findall(f"{ns_main}c"):
                ref = c_el.attrib.get("r", "A1")
                c_idx = col_letters_to_idx(ref)
                max_col = max(max_col, c_idx + 1)
                c_type = c_el.attrib.get("t", "")
                v_el = c_el.find(f"{ns_main}v")
                is_el = c_el.find(f"{ns_main}is")
                val: Any = None
                if c_type == "s" and v_el is not None and v_el.text is not None:
                    s_idx = int(v_el.text)
                    val = shared_strings[s_idx] if 0 <= s_idx < len(shared_strings) else ""
                elif c_type == "inlineStr" and is_el is not None:
                    val = "".join(t.text or "" for t in is_el.iter(f"{ns_main}t"))
                elif v_el is not None:
                    val = v_el.text
                row_dict[c_idx] = val
            if row_dict:
                rows_raw.append(row_dict)

        if not rows_raw:
            return pd.DataFrame()

        header_vals = [
            str(rows_raw[0].get(i) or f"Column_{i + 1}").strip()
            for i in range(max_col)
        ]
        body = [
            [r.get(i) for i in range(max_col)]
            for r in rows_raw[1:]
        ]
        return pd.DataFrame(body, columns=header_vals)


def _read_xml_or_xmx(path: Path) -> pd.DataFrame:
    """Parse XML / XMX / MXML files (nested trace/event logs OR flat record tables)."""
    tree = ET.parse(path)
    root = tree.getroot()
    root_tag = _strip_ns(root.tag).lower()

    # Case 1: XES-style <log><trace><event>
    traces = [el for el in root if _strip_ns(el.tag).lower() == "trace"]
    if traces:
        records: list[dict[str, Any]] = []
        for t_idx, trace_el in enumerate(traces, start=1):
            trace_attrs: dict[str, Any] = {}
            for child in trace_el:
                ctag = _strip_ns(child.tag).lower()
                if ctag != "event" and "key" in child.attrib:
                    k = child.attrib["key"]
                    trace_attrs[f"case:{k}" if k != "concept:name" else CASE_ID_ATTRIBUTE] = child.attrib.get("value")
            cid = trace_attrs.get(CASE_ID_ATTRIBUTE, f"Case_{t_idx}")
            for ev_el in trace_el:
                if _strip_ns(ev_el.tag).lower() != "event":
                    continue
                row = dict(trace_attrs)
                row[CASE_ID_ATTRIBUTE] = cid
                for prop in ev_el:
                    if "key" in prop.attrib:
                        row[prop.attrib["key"]] = prop.attrib.get("value")
                records.append(row)
        return pd.DataFrame(records)

    # Case 2: ProM MXML / XMX <WorkflowLog><Process><ProcessInstance><AuditTrailEntry>
    instances = [el for el in root.iter() if _strip_ns(el.tag).lower() == "processinstance"]
    if instances:
        records = []
        for idx, inst in enumerate(instances, start=1):
            cid = inst.attrib.get("id") or f"Case_{idx}"
            for ate in inst:
                if _strip_ns(ate.tag).lower() != "audittrailentry":
                    continue
                row: dict[str, Any] = {"Case ID": cid}
                for child in ate:
                    cname = _strip_ns(child.tag)
                    lname = cname.lower()
                    if lname == "workflowmodelelement":
                        row["Activity"] = (child.text or "").strip()
                    elif lname == "eventtype":
                        row["Lifecycle"] = (child.text or "").strip()
                    elif lname == "timestamp":
                        row["Timestamp"] = (child.text or "").strip()
                    elif lname == "originator":
                        row["Resource"] = (child.text or "").strip()
                    elif lname == "data":
                        for attr in child:
                            aname = attr.attrib.get("name") or _strip_ns(attr.tag)
                            row[aname] = (attr.text or "").strip()
                    else:
                        row[cname] = (child.text or "").strip()
                records.append(row)
        return pd.DataFrame(records)

    # Case 3: Generic flat XML (<rows><row><col>val</col></row></rows> or attributes)
    records = []
    for child in root:
        row_data: dict[str, Any] = dict(child.attrib)
        for sub in child:
            sname = _strip_ns(sub.tag)
            if list(sub):
                for leaf in sub:
                    row_data[f"{sname}_{_strip_ns(leaf.tag)}"] = (leaf.text or "").strip()
            else:
                row_data[sname] = (sub.text or "").strip()
        if row_data:
            records.append(row_data)

    if records:
        return pd.DataFrame(records)

    raise ValueError(f"Could not extract tabular event records from '{path.name}'.")


def _detect_csv_delimiter(path: Path, encoding: str) -> str:
    try:
        with path.open("r", encoding=encoding, errors="replace") as handle:
            sample = handle.read(8192)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except Exception:
        return ","


def read_raw_data_file(
    file_path: str | Path,
    *,
    encoding: str = "utf-8",
    delimiter: str = "auto",
    use_quotes: bool = True,
    extract_dir: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read any supported event/data file into a DataFrame plus source metadata."""
    if not isinstance(file_path, (str, Path)) or not str(file_path).strip():
        raise ValueError("Please provide a valid path to a data file.")

    path = Path(file_path).expanduser()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    lower_name = path.name.lower()

    # 1. XES / XES.GZ -> delegate to validated XES loader
    if lower_name.endswith(".xes") or lower_name.endswith(".xes.gz"):
        target_xes = path
        if lower_name.endswith(".xes.gz"):
            out_dir = extract_dir or (path.resolve().parent / "data")
            out_dir.mkdir(parents=True, exist_ok=True)
            extracted = out_dir / path.name[:-3]
            if not extracted.exists():
                with gzip.open(path, "rb") as fin, extracted.open("wb") as fout:
                    shutil.copyfileobj(fin, fout)
            target_xes = extracted
        df, meta = load_xes(target_xes)
        info = dict(meta)
        info["is_xes"] = True
        info["source_path"] = str(path)
        return df, info

    # 2. CSV / TSV / TXT
    if is_csv_like_path(path):
        sep = delimiter
        if sep in ("auto", "Auto-detect", ""):
            if lower_name.endswith(".tsv"):
                sep = "\t"
            elif not lower_name.endswith(".gz"):
                sep = _detect_csv_delimiter(path, encoding)
            else:
                sep = ","
        quoting = csv.QUOTE_MINIMAL if use_quotes else csv.QUOTE_NONE
        df = pd.read_csv(
            path,
            sep=sep,
            encoding=encoding,
            quoting=quoting,
            low_memory=False,
        )
    # 3. Excel (.xlsx, .xlsm, .xls)
    elif lower_name.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            df = pd.read_excel(path)
        except ImportError:
            if lower_name.endswith((".xlsx", ".xlsm")):
                df = _read_xlsx_stdlib_fallback(path)
            else:
                raise RuntimeError(
                    "Reading legacy .xls files requires 'xlrd' or saving as .xlsx / .csv."
                )
    # 4. XML / XMX / MXML
    elif lower_name.endswith((".xml", ".xmx", ".mxml")):
        df = _read_xml_or_xmx(path)
    # 5. JSON / JSONL
    elif lower_name.endswith(".jsonl"):
        df = pd.read_json(path, lines=True)
    elif lower_name.endswith(".json"):
        df = pd.read_json(path)
    # 6. Parquet
    elif lower_name.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        # Last-resort attempt as delimited text
        sep = _detect_csv_delimiter(path, encoding)
        df = pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)

    if df.empty:
        raise ValueError(f"File '{path.name}' contains 0 rows.")

    # Forward-fill blank Case IDs if grouped-table style (like merged Excel/Disco procurement logs!)
    info = {
        "file_name": path.name,
        "row_count": len(df),
        "columns": [str(c) for c in df.columns],
        "is_xes": False,
        "source_path": str(path),
    }
    return df, info


def detect_column_roles(df: pd.DataFrame) -> dict[str, str]:
    """Heuristically guess Disco column roles from column names and sample values."""
    roles: dict[str, str] = {}
    cols = [str(c) for c in df.columns]

    case_assigned = False
    act_assigned = False
    ts_assigned = False
    res_assigned = False
    lc_assigned = False

    # Exact XES standard names first
    for col in cols:
        cl = col.strip().lower()
        if col == CASE_ID_ATTRIBUTE:
            roles[col] = ROLE_CASE
            case_assigned = True
        elif col == ACTIVITY_ATTRIBUTE:
            roles[col] = ROLE_ACTIVITY
            act_assigned = True
        elif col == TIMESTAMP_ATTRIBUTE:
            roles[col] = ROLE_TIMESTAMP
            ts_assigned = True
        elif col == RESOURCE_ATTRIBUTE:
            roles[col] = ROLE_RESOURCE
            res_assigned = True
        elif col == LIFECYCLE_ATTRIBUTE:
            roles[col] = ROLE_LIFECYCLE
            lc_assigned = True

    # Common tabular header patterns
    case_pat = re.compile(r"\b(case[_\s-]*id|case|trace[_\s-]*id|order[_\s-]*id|application[_\s-]*id|id)\b", re.I)
    act_pat = re.compile(r"\b(activity|action|event[_\s-]*name|task|step|operation|status[_\s-]*name)\b", re.I)
    explicit_ts_pat = re.compile(r"(timestamp|date[_\s-]*time)", re.I)
    any_ts_pat = re.compile(r"\b(time|date|start|end|created_at|updated_at)\b", re.I)
    res_pat = re.compile(r"\b(resource|person|user|agent|officer|employee|actor|originator|assignee)\b", re.I)
    lc_pat = re.compile(r"\b(lifecycle|transition|event[_\s-]*type|state)\b", re.I)

    for col in cols:
        if col in roles:
            continue
        if not case_assigned and case_pat.search(col):
            roles[col] = ROLE_CASE
            case_assigned = True
        elif not act_assigned and act_pat.search(col):
            roles[col] = ROLE_ACTIVITY
            act_assigned = True
        elif explicit_ts_pat.search(col):
            # Like Disco, assign Timestamp role to explicit Timestamp columns
            # (e.g. both 'Start Timestamp' and 'Complete Timestamp')
            roles[col] = ROLE_TIMESTAMP
            ts_assigned = True
        elif not res_assigned and res_pat.search(col):
            roles[col] = ROLE_RESOURCE
            res_assigned = True
        elif not lc_assigned and lc_pat.search(col):
            roles[col] = ROLE_LIFECYCLE
            lc_assigned = True

    # Second pass for timestamp if only generic 'start' / 'date' exists
    if not ts_assigned:
        for col in cols:
            if col not in roles and any_ts_pat.search(col):
                roles[col] = ROLE_TIMESTAMP
                ts_assigned = True
                break

    # Fallbacks if still unassigned: pick first 3 columns
    remaining = [c for c in cols if c not in roles]
    if not case_assigned and remaining:
        roles[remaining.pop(0)] = ROLE_CASE
    if not act_assigned and remaining:
        roles[remaining.pop(0)] = ROLE_ACTIVITY
    if not ts_assigned and remaining:
        roles[remaining.pop(0)] = ROLE_TIMESTAMP

    for col in cols:
        roles.setdefault(col, ROLE_OTHER)

    return roles


def parse_flexible_timestamps(
    series: pd.Series,
    timestamp_format: str | None = None,
) -> pd.Series:
    """Parse timestamps supporting explicit patterns, ISO-8601, and DD/MM/YYYY."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce", utc=True)

    fmt = TIMESTAMP_FORMATS.get(timestamp_format or "", timestamp_format)
    if fmt:
        return pd.to_datetime(series, format=fmt, errors="coerce", utc=True)

    # Auto-detect: check if slash-separated dates look like DD/MM/YYYY (e.g. 16/02/2011)
    sample = series.dropna().astype(str).head(50)
    dayfirst = False
    slash_dates = [s for s in sample if re.match(r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", s)]
    if slash_dates:
        for s in slash_dates:
            first_part = int(re.split(r"[/.-]", s)[0])
            if first_part > 12:
                dayfirst = True
                break
        else:
            # Default European/Indonesian DD/MM/YYYY for slash dates like Disco
            dayfirst = True

    try:
        return pd.to_datetime(
            series,
            errors="coerce",
            utc=True,
            dayfirst=dayfirst,
            format="mixed",
        )
    except (TypeError, ValueError):
        return pd.to_datetime(series, errors="coerce", utc=True, dayfirst=dayfirst)


def _combine_columns(df: pd.DataFrame, cols: Sequence[str], sep: str) -> pd.Series:
    if len(cols) == 1:
        s = df[cols[0]]
        return s.where(s.notna(), None)

    parts = [df[c].where(df[c].notna(), "").astype(str).str.strip() for c in cols]
    combined = parts[0]
    for p in parts[1:]:
        combined = combined.where(p == "", combined + sep + p).where(
            combined != "", p
        )
    return combined.where(combined != "", None)


def apply_column_mapping(
    raw_df: pd.DataFrame,
    role_map: Mapping[str, str],
    *,
    timestamp_format: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Transform ``raw_df`` into a validated XES-contract event DataFrame.

    Strictly enforces the three foundational Process Mining event-log
    cardinality rules (non-OCPM):
    1. **Exactly 1 Case ID (`len(case_cols) == 1` & non-empty per event)**:
       Events without a Case ID (orphan events) are rejected/filtered out, and
       assigning 0 or >1 Case ID columns raises ``ValueError``.
    2. **At least 1 Activity (`len(act_cols) >= 1` & non-empty per event/case)**:
       Events without an Activity are rejected/filtered out so every surviving
       case has >= 1 valid activity.
    3. **At least 1 Timestamp (`len(ts_cols) >= 1` & >= 1 valid timestamp per event)**:
       Events with no valid timestamp are rejected/filtered out. When 2+
       timestamp columns are mapped (e.g. Start + Complete Timestamp), the
       earliest timestamp is stored in ``time:start_timestamp`` and the latest
       in ``time:timestamp`` to enable both **Service Time** and **Waiting Time**
       calculation.
    """
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        raise ValueError("Source DataFrame is empty.")

    case_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_CASE]
    act_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_ACTIVITY]
    ts_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_TIMESTAMP]
    res_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_RESOURCE]
    lc_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_LIFECYCLE]
    other_cols = [c for c in raw_df.columns if role_map.get(str(c)) == ROLE_OTHER]

    # --- Cardinality Rule Validation (Column Level) ---
    cardinality_errors: list[str] = []
    if len(case_cols) == 0:
        cardinality_errors.append("Exactly 1 Case ID column is required (found 0)")
    elif len(case_cols) > 1:
        cardinality_errors.append(
            f"Exactly 1 Case ID column is allowed per event (found {len(case_cols)}: "
            + ", ".join(map(str, case_cols))
            + ")"
        )
    if len(act_cols) < 1:
        cardinality_errors.append("At least 1 Activity column is required (found 0)")
    if len(ts_cols) < 1:
        cardinality_errors.append("At least 1 Timestamp column is required (found 0)")

    if cardinality_errors:
        raise ValueError(
            "Process mining cardinality rule violation: "
            + "; ".join(cardinality_errors)
            + "."
        )

    out = pd.DataFrame(index=raw_df.index)

    # 1. Exactly 1 Case ID (no ffill fabrication on orphan rows!)
    raw_case = raw_df[case_cols[0]]
    case_clean = raw_case.where(raw_case.notna(), "").astype(str).str.strip()
    out[CASE_ID_ATTRIBUTE] = case_clean.where(case_clean != "", None)

    # 2. At least 1 Activity
    act_raw = _combine_columns(raw_df, act_cols, " - ")
    act_clean = act_raw.where(act_raw.notna(), "").astype(str).str.strip()
    out[ACTIVITY_ATTRIBUTE] = act_clean.where(act_clean != "", None)

    # 3. At least 1 Timestamp (supports single atomic timestamp OR Start + Complete timestamps)
    parsed_ts_list = [
        (str(col), parse_flexible_timestamps(raw_df[col], timestamp_format))
        for col in ts_cols
    ]
    if len(parsed_ts_list) == 1:
        out[TIMESTAMP_ATTRIBUTE] = parsed_ts_list[0][1]
        has_dual_ts = False
    else:
        ts_matrix = pd.concat([pts for _c, pts in parsed_ts_list], axis=1)
        start_ts = ts_matrix.min(axis=1)
        complete_ts = ts_matrix.max(axis=1)
        out[TIMESTAMP_ATTRIBUTE] = complete_ts
        out[START_TIMESTAMP_ATTRIBUTE] = start_ts
        has_dual_ts = True
        for col_name, pts in parsed_ts_list:
            if col_name not in (
                CASE_ID_ATTRIBUTE,
                ACTIVITY_ATTRIBUTE,
                TIMESTAMP_ATTRIBUTE,
                START_TIMESTAMP_ATTRIBUTE,
            ):
                out[col_name] = pts

    # Optional Resource (Person)
    if res_cols:
        out[RESOURCE_ATTRIBUTE] = _combine_columns(raw_df, res_cols, " / ")

    # Optional Lifecycle
    if lc_cols:
        out[LIFECYCLE_ATTRIBUTE] = _combine_columns(raw_df, lc_cols, "_")

    # Other preserved columns (never overwrite core mapped names)
    reserved = set(out.columns)
    for col in other_cols:
        col_name = str(col)
        target_name = col_name if col_name not in reserved else f"attr:{col_name}"
        out[target_name] = raw_df[col]
        reserved.add(target_name)

    # --- Cardinality Rule Validation (Row / Event Level) ---
    has_case = out[CASE_ID_ATTRIBUTE].notna()
    has_act = out[ACTIVITY_ATTRIBUTE].notna()
    has_ts = out[TIMESTAMP_ATTRIBUTE].notna()

    orphan_dropped = int((~has_case).sum())
    missing_act_dropped = int((has_case & ~has_act).sum())
    missing_ts_dropped = int((has_case & has_act & ~has_ts).sum())

    valid_mask = has_case & has_act & has_ts
    out = out.loc[valid_mask].copy()
    if out.empty:
        raise ValueError(
            "No valid events remained after enforcing process mining cardinality "
            f"(orphan events without Case ID: {orphan_dropped}, "
            f"missing Activity: {missing_act_dropped}, "
            f"missing/invalid Timestamp: {missing_ts_dropped})."
        )

    out[CASE_ID_ATTRIBUTE] = out[CASE_ID_ATTRIBUTE].astype(str)
    out[ACTIVITY_ATTRIBUTE] = out[ACTIVITY_ATTRIBUTE].astype(str)

    # Stable chronological ordering by Case ID, Timestamp, Start Timestamp (if dual), & source order
    order_col = "__importer_row_order__"
    out[order_col] = range(len(out))
    sort_cols = (
        [CASE_ID_ATTRIBUTE, START_TIMESTAMP_ATTRIBUTE, TIMESTAMP_ATTRIBUTE, order_col]
        if has_dual_ts
        else [CASE_ID_ATTRIBUTE, TIMESTAMP_ATTRIBUTE, order_col]
    )
    out = (
        out.sort_values(
            by=sort_cols,
            kind="mergesort",
            na_position="last",
        )
        .drop(columns=[order_col])
        .reset_index(drop=True)
    )

    warnings: list[str] = []
    if orphan_dropped > 0:
        warnings.append(f"Dropped {orphan_dropped:,} orphan event(s) missing Case ID.")
    if missing_act_dropped > 0:
        warnings.append(f"Dropped {missing_act_dropped:,} event(s) missing Activity.")
    if missing_ts_dropped > 0:
        warnings.append(f"Dropped {missing_ts_dropped:,} event(s) missing a valid Timestamp.")

    optional_present = validate_event_dataframe(out)
    metadata = {
        "case_count": int(out[CASE_ID_ATTRIBUTE].nunique()),
        "event_count": len(out),
        "attributes": [str(c) for c in out.columns],
        "optional_attributes": list(optional_present),
        "has_dual_timestamps": has_dual_ts,
        "orphan_events_dropped": orphan_dropped,
        "missing_activity_dropped": missing_act_dropped,
        "missing_timestamp_dropped": missing_ts_dropped,
        "warnings": warnings,
    }
    return out, metadata


__all__ = [
    "ROLE_ACTIVITY",
    "ROLE_CASE",
    "ROLE_IGNORE",
    "ROLE_LIFECYCLE",
    "ROLE_OTHER",
    "ROLE_RESOURCE",
    "ROLE_TIMESTAMP",
    "START_TIMESTAMP_ATTRIBUTE",
    "SUPPORTED_FILE_FILTER",
    "TIMESTAMP_FORMATS",
    "VALID_ROLES",
    "apply_column_mapping",
    "detect_column_roles",
    "is_csv_like_path",
    "is_xes_path",
    "parse_flexible_timestamps",
    "read_raw_data_file",
]
