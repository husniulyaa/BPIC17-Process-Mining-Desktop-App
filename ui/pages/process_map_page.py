"""Interactive Fluxicon Disco-inspired Process Map page with Sugiyama layout.

Key features modeled directly after Fluxicon Disco:
- Default Activities = 100%, Paths = 0% (clean maximal spanning process backbone
  without spaghetti crossings; dragging Paths % progressively reveals secondary
  transitions).
- True Sugiyama hierarchical layout:
    1. Trace-ordered cycle breaking & dominant-backbone longest-path ranking
       (produces a crisp vertical process spine with natural branches).
    2. Alternating barycenter sweeps for crossing minimization.
    3. Parent-aligned continuous X coordinate relaxation with collision spacing.
- Port spreading on hub nodes, bidirectional lens arcs (u <-> v), obstacle-aware
  bypass curves for long-span shortcuts, teardrop self-loops, and debounced
  slider updates.
- Routed through ``GLOBAL_TASK_SCHEDULER`` so large logs never freeze the UI.
"""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np
import pandas as pd
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
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
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.data_contract import (
    ACTIVITY_ATTRIBUTE,
    CASE_ID_ATTRIBUTE,
    TIMESTAMP_ATTRIBUTE,
    validate_event_dataframe,
)
from ui.disco_widgets import DiscoSegmentedToggle, make_disco_search
from ui.task_scheduler import GLOBAL_TASK_SCHEDULER
from utils.case_timeline import format_human_duration

START_NODE = "__START__"
END_NODE = "__END__"


def compute_process_map_data(event_df: pd.DataFrame) -> dict[str, Any]:
    """Compute Directly-Follows Graph (DFG) metrics using fast C/NumPy operations."""
    validate_event_dataframe(event_df, allow_empty=True)
    if event_df.empty:
        return {
            "activities": {},
            "edges": [],
            "start_edges": {},
            "end_edges": {},
            "total_cases": 0,
        }

    valid_mask = event_df[CASE_ID_ATTRIBUTE].notna() & event_df[ACTIVITY_ATTRIBUTE].notna()
    if not valid_mask.any():
        return {
            "activities": {},
            "edges": [],
            "start_edges": {},
            "end_edges": {},
            "total_cases": 0,
        }

    sub = event_df.loc[valid_mask, [CASE_ID_ATTRIBUTE, ACTIVITY_ATTRIBUTE, TIMESTAMP_ATTRIBUTE]]
    ts_col = sub[TIMESTAMP_ATTRIBUTE]
    if isinstance(ts_col.dtype, pd.DatetimeTZDtype) and str(ts_col.dtype.tz) == "UTC":
        ts = ts_col
    else:
        try:
            ts = pd.to_datetime(ts_col, errors="coerce", utc=True, format="mixed")
        except (TypeError, ValueError):
            ts = pd.to_datetime(ts_col, errors="coerce", utc=True)

    df = pd.DataFrame(
        {
            "_cid": pd.Categorical(sub[CASE_ID_ATTRIBUTE].astype(str)),
            "_act": pd.Categorical(sub[ACTIVITY_ATTRIBUTE].astype(str).str.strip()),
            "_ts": ts,
            "_ord": np.arange(len(sub), dtype=np.int64),
        }
    )

    if not df.set_index(["_cid", "_ts"]).index.is_monotonic_increasing:
        df = df.sort_values(
            by=["_cid", "_ts", "_ord"],
            kind="mergesort",
            na_position="last",
        ).reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    time.sleep(0)

    total_cases = int(df["_cid"].nunique())
    grp = df.groupby("_cid", sort=False, observed=True)
    pos = grp.cumcount()
    sizes = grp["_act"].transform("size")
    df["_rel_pos"] = pos / (sizes - 1).clip(lower=1)

    act_agg = df.groupby("_act", sort=False, observed=True).agg(
        abs_freq=("_act", "size"),
        case_freq=("_cid", "nunique"),
        avg_pos=("_rel_pos", "mean"),
    )
    activities: dict[str, dict[str, Any]] = {}
    for act_name, abs_f, case_f, avg_p in zip(
        act_agg.index.astype(str),
        act_agg["abs_freq"].to_numpy(),
        act_agg["case_freq"].to_numpy(),
        act_agg["avg_pos"].to_numpy(),
    ):
        activities[str(act_name)] = {
            "abs_freq": int(abs_f),
            "case_freq": int(case_f),
            "avg_pos": float(avg_p),
        }

    first_acts = grp["_act"].first().value_counts()
    last_acts = grp["_act"].last().value_counts()
    start_edges = {str(k): int(v) for k, v in first_acts.items() if int(v) > 0}
    end_edges = {str(k): int(v) for k, v in last_acts.items() if int(v) > 0}

    time.sleep(0)

    cid_codes = df["_cid"].cat.codes.to_numpy()
    same_case = cid_codes[:-1] == cid_codes[1:]

    src_arr = df["_act"].iloc[:-1].to_numpy()[same_case]
    dst_arr = df["_act"].iloc[1:].to_numpy()[same_case]
    cid_same = df["_cid"].iloc[:-1].to_numpy()[same_case]

    t0 = df["_ts"].iloc[:-1].reset_index(drop=True)
    t1 = df["_ts"].iloc[1:].reset_index(drop=True)
    dur_all = (t1 - t0).dt.total_seconds().to_numpy()[same_case]
    dur_all = np.where(np.isnan(dur_all), np.nan, np.maximum(0.0, dur_all))

    trans_df = pd.DataFrame(
        {
            "cid": pd.Categorical(cid_same),
            "src": pd.Categorical(src_arr),
            "dst": pd.Categorical(dst_arr),
            "dur_sec": dur_all,
        }
    )

    edges: list[dict[str, Any]] = []
    if not trans_df.empty:
        edge_agg = trans_df.groupby(["src", "dst"], sort=False, observed=True).agg(
            abs_freq=("src", "size"),
            case_freq=("cid", "nunique"),
            mean_sec=("dur_sec", "mean"),
            total_sec=("dur_sec", "sum"),
        )
        idx_tuples = edge_agg.index.tolist()
        for (src, dst), abs_f, case_f, m_sec, t_sec in zip(
            idx_tuples,
            edge_agg["abs_freq"].to_numpy(),
            edge_agg["case_freq"].to_numpy(),
            edge_agg["mean_sec"].to_numpy(),
            edge_agg["total_sec"].to_numpy(),
        ):
            edges.append(
                {
                    "src": str(src),
                    "dst": str(dst),
                    "abs_freq": int(abs_f),
                    "case_freq": int(case_f),
                    "mean_sec": None if np.isnan(m_sec) else float(m_sec),
                    "total_sec": 0.0 if np.isnan(t_sec) else float(t_sec),
                }
            )

    return {
        "activities": activities,
        "edges": edges,
        "start_edges": start_edges,
        "end_edges": end_edges,
        "total_cases": total_cases,
    }


def _select_disco_backbone_edges(
    kept_acts: dict[str, dict[str, Any]],
    non_self: list[dict[str, Any]],
    start_edges: dict[str, int],
    end_edges: dict[str, int],
    path_pct: float,
) -> list[dict[str, Any]]:
    """Select edges using Fluxicon Disco's spanning-backbone + slider logic."""
    if not non_self:
        return []

    primary_start = max(start_edges, key=start_edges.get) if start_edges else None
    primary_end = max(end_edges, key=end_edges.get) if end_edges else None

    backbone_pairs: set[tuple[str, str]] = set()

    # 1. Strongest incoming & strongest outgoing edge per visible activity
    for act in kept_acts:
        if act != primary_start:
            inc = [e for e in non_self if e["dst"] == act]
            if inc:
                best_in = max(inc, key=lambda e: e["abs_freq"])
                backbone_pairs.add((best_in["src"], best_in["dst"]))
        if act != primary_end:
            out = [e for e in non_self if e["src"] == act]
            if out:
                best_out = max(out, key=lambda e: e["abs_freq"])
                backbone_pairs.add((best_out["src"], best_out["dst"]))

    # 2. Ensure weak connectivity across all kept activities via Kruskal bridges
    parent = {a: a for a in kept_acts}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    for u, v in backbone_pairs:
        union(u, v)

    sorted_edges = sorted(non_self, key=lambda e: -e["abs_freq"])
    for e in sorted_edges:
        if union(e["src"], e["dst"]):
            backbone_pairs.add((e["src"], e["dst"]))

    # 3. Progressive addition above Paths = 0% using smooth power curve
    remaining = [e for e in sorted_edges if (e["src"], e["dst"]) not in backbone_pairs]
    extra_n = int(round(len(remaining) * (path_pct ** 1.4))) if path_pct > 0 else 0

    selected = [e for e in sorted_edges if (e["src"], e["dst"]) in backbone_pairs]
    selected.extend(remaining[:extra_n])
    return selected


def _compute_sugiyama_layout(
    kept_acts: dict[str, dict[str, Any]],
    shown_edges: list[dict[str, Any]],
    start_edges: dict[str, int],
    end_edges: dict[str, int],
    *,
    node_w: float,
    x_gap: float = 68.0,
    y_step: float = 92.0,
) -> tuple[dict[str, QPointF], dict[str, int], list[list[str]]]:
    """Compute a clean hierarchical Sugiyama layout matching Fluxicon Disco."""
    names = list(kept_acts.keys())
    if not names:
        return {}, {}, []

    # Order activities along natural process progression (entry -> trace pos -> exit)
    max_start = max(start_edges.values(), default=1) or 1
    max_end = max(end_edges.values(), default=1) or 1

    def flow_score(act: str) -> float:
        base = float(kept_acts[act]["avg_pos"])
        s_bonus = -0.25 * (start_edges.get(act, 0) / max_start)
        e_bonus = 0.20 * (end_edges.get(act, 0) / max_end)
        return base + s_bonus + e_bonus

    ordered = sorted(names, key=lambda a: (flow_score(a), -kept_acts[a]["abs_freq"], a))
    order_idx = {a: i for i, a in enumerate(ordered)}

    # Build forward DAG for ranking:
    # Keep edges moving forward in flow_score; for near-ties, orient heavier->lighter
    edge_lookup = {(e["src"], e["dst"]): e["abs_freq"] for e in shown_edges}
    forward_adj: dict[str, list[tuple[str, int]]] = {a: [] for a in names}
    out_totals: dict[str, int] = {a: 0 for a in names}
    for e in shown_edges:
        out_totals[e["src"]] += int(e["abs_freq"])

    for e in shown_edges:
        u, v, w = e["src"], e["dst"], int(e["abs_freq"])
        rev_w = edge_lookup.get((v, u), 0)
        score_diff = flow_score(v) - flow_score(u)
        if rev_w > 0:
            # Bidirectional pair: orient heavier direction forward (break tie by order_idx)
            is_fwd = (w > rev_w) or (w == rev_w and order_idx[u] < order_idx[v])
        else:
            is_fwd = order_idx[u] < order_idx[v] or score_diff > 0.02

        if is_fwd:
            forward_adj[u].append((v, w))

    # Dominant-backbone longest-path rank assignment:
    # Use each node's strongest incoming forward edge + major outgoing forward edges
    # (>= 12% of source outflow) so rare shortcut edges don't distort the main spine!
    rank_edges: dict[str, list[str]] = {a: [] for a in names}
    best_in_parent: dict[str, tuple[str, int]] = {}
    for u in ordered:
        tot_out = max(1, out_totals[u])
        for v, w in forward_adj[u]:
            if order_idx[u] < order_idx[v]:
                if w / tot_out >= 0.12:
                    rank_edges[u].append(v)
                prev = best_in_parent.get(v)
                if prev is None or w > prev[1]:
                    best_in_parent[v] = (u, w)

    for v, (u, _w) in best_in_parent.items():
        if v not in rank_edges[u]:
            rank_edges[u].append(v)

    ranks: dict[str, int] = {a: 0 for a in names}
    for u in ordered:
        for v in rank_edges[u]:
            if ranks[v] < ranks[u] + 1:
                ranks[v] = min(16, ranks[u] + 1)

    # Compact empty ranks
    used_ranks = sorted(set(ranks.values()))
    remap = {old_r: new_r for new_r, old_r in enumerate(used_ranks)}
    for a in names:
        ranks[a] = remap[ranks[a]]

    max_rank = max(ranks.values(), default=0)
    layers: list[list[str]] = [[] for _ in range(max_rank + 1)]
    for a in ordered:
        layers[ranks[a]].append(a)

    # Neighbor maps across ALL shown edges between distinct ranks for barycenter sweeps
    preds: dict[str, list[tuple[str, float]]] = {a: [] for a in names}
    succs: dict[str, list[tuple[str, float]]] = {a: [] for a in names}
    for e in shown_edges:
        u, v = e["src"], e["dst"]
        w = math.sqrt(max(1.0, float(e["abs_freq"])))
        if ranks[u] < ranks[v]:
            succs[u].append((v, w))
            preds[v].append((u, w))
        elif ranks[v] < ranks[u]:
            succs[v].append((u, w))
            preds[u].append((v, w))

    # Barycenter crossing-minimization sweeps (12 alternating passes)
    pos_in_layer: dict[str, float] = {}
    for lyr in layers:
        for idx, a in enumerate(lyr):
            pos_in_layer[a] = float(idx)

    for sweep in range(12):
        if sweep % 2 == 0:
            for r in range(1, len(layers)):
                lyr = layers[r]
                scored = []
                for a in lyr:
                    nb = preds[a]
                    if nb:
                        bary = sum(pos_in_layer[p] * w for p, w in nb) / sum(
                            w for _, w in nb
                        )
                    else:
                        bary = pos_in_layer[a]
                    scored.append((bary, -kept_acts[a]["abs_freq"], a))
                scored.sort()
                layers[r] = [a for _, _, a in scored]
                for idx, a in enumerate(layers[r]):
                    pos_in_layer[a] = float(idx)
        else:
            for r in range(len(layers) - 2, -1, -1):
                lyr = layers[r]
                scored = []
                for a in lyr:
                    nb = succs[a]
                    if nb:
                        bary = sum(pos_in_layer[s] * w for s, w in nb) / sum(
                            w for _, w in nb
                        )
                    else:
                        bary = pos_in_layer[a]
                    scored.append((bary, -kept_acts[a]["abs_freq"], a))
                scored.sort()
                layers[r] = [a for _, _, a in scored]
                for idx, a in enumerate(layers[r]):
                    pos_in_layer[a] = float(idx)

    # Continuous X coordinate assignment with parent/child pull & collision spacing
    min_sep = node_w + x_gap
    x_coords: dict[str, float] = {}
    for lyr in layers:
        total_w = (len(lyr) - 1) * min_sep
        for idx, a in enumerate(lyr):
            x_coords[a] = -total_w / 2.0 + idx * min_sep

    def resolve_layer_collisions(lyr: list[str]) -> None:
        if len(lyr) <= 1:
            return
        # Left-to-right push
        for i in range(1, len(lyr)):
            prev_a, cur_a = lyr[i - 1], lyr[i]
            if x_coords[cur_a] - x_coords[prev_a] < min_sep:
                x_coords[cur_a] = x_coords[prev_a] + min_sep
        # Recenter around desired mean
        desired_mid = sum(x_coords[a] for a in lyr) / len(lyr)
        actual_mid = (x_coords[lyr[0]] + x_coords[lyr[-1]]) / 2.0
        shift = desired_mid - actual_mid
        for a in lyr:
            x_coords[a] += shift

    for it in range(10):
        # Top-down parent alignment
        for r in range(1, len(layers)):
            for a in layers[r]:
                nb = preds[a]
                if nb:
                    target_x = sum(x_coords[p] * w for p, w in nb) / sum(
                        w for _, w in nb
                    )
                    x_coords[a] = 0.30 * x_coords[a] + 0.70 * target_x
            resolve_layer_collisions(layers[r])

        # Bottom-up child alignment (gentler weight so top spine stays straight!)
        for r in range(len(layers) - 2, -1, -1):
            for a in layers[r]:
                nb = succs[a]
                if nb:
                    target_x = sum(x_coords[s] * w for s, w in nb) / sum(
                        w for _, w in nb
                    )
                    blend = 0.25 if len(layers[r]) == 1 else 0.45
                    x_coords[a] = (1.0 - blend) * x_coords[a] + blend * target_x
            resolve_layer_collisions(layers[r])

    # Align Start above primary entry node and End below primary exit node
    primary_start = max(
        (a for a in names if a in start_edges),
        key=lambda a: start_edges[a],
        default=layers[0][0],
    )
    primary_end = max(
        (a for a in names if a in end_edges),
        key=lambda a: end_edges[a],
        default=layers[-1][0],
    )

    positions: dict[str, QPointF] = {
        START_NODE: QPointF(x_coords[primary_start], 0.0),
    }
    for r, lyr in enumerate(layers):
        y = (r + 1) * y_step
        for a in lyr:
            positions[a] = QPointF(x_coords[a], y)

    positions[END_NODE] = QPointF(
        x_coords[primary_end],
        (len(layers) + 1) * y_step + 12.0,
    )
    return positions, ranks, layers


class _ZoomableGraphView(QGraphicsView):
    zoom_changed = Signal(int)

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setStyleSheet("QGraphicsView { background: #FFFFFF; border: none; }")
        self._zoom_pct = 100

    def set_zoom_percent(self, pct: int) -> None:
        pct = max(20, min(250, int(pct)))
        self._zoom_pct = pct
        self.resetTransform()
        scale = pct / 100.0
        self.scale(scale, scale)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = 10 if event.angleDelta().y() > 0 else -10
        new_pct = max(20, min(230, self._zoom_pct + delta))
        if new_pct != self._zoom_pct:
            self.set_zoom_percent(new_pct)
            self.zoom_changed.emit(new_pct)
        event.accept()


class _LegendRampWidget(QWidget):
    """Dual Disco visual ramp showing node & path scale in the Detail panel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(92)
        self._mode = "frequency"
        self._max_node_txt = "0"
        self._max_edge_txt = "0"

    def set_legend(self, mode: str, max_node_txt: str, max_edge_txt: str) -> None:
        self._mode = mode
        self._max_node_txt = max_node_txt
        self._max_edge_txt = max_edge_txt
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()
        cx = w / 2.0

        left_poly = QPolygonF(
            [
                QPointF(cx - 26, 8),
                QPointF(cx - 4, 8),
                QPointF(cx - 4, 82),
                QPointF(cx - 12, 82),
            ]
        )
        grad_l = QLinearGradient(0, 8, 0, 82)
        if self._mode == "performance":
            grad_l.setColorAt(0.0, QColor("#9C2222"))
            grad_l.setColorAt(0.5, QColor("#DE8738"))
            grad_l.setColorAt(1.0, QColor("#F2E6DA"))
        else:
            grad_l.setColorAt(0.0, QColor("#074875"))
            grad_l.setColorAt(0.45, QColor("#3A7CB8"))
            grad_l.setColorAt(1.0, QColor("#EAECEF"))

        painter.setPen(QPen(QColor("#8E959C"), 1.0))
        painter.setBrush(grad_l)
        painter.drawPolygon(left_poly)

        right_poly = QPolygonF(
            [
                QPointF(cx + 4, 8),
                QPointF(cx + 26, 8),
                QPointF(cx + 12, 82),
                QPointF(cx + 4, 82),
            ]
        )
        grad_r = QLinearGradient(0, 8, 0, 82)
        grad_r.setColorAt(0.0, QColor("#22262A"))
        grad_r.setColorAt(1.0, QColor("#D2D7DD"))
        painter.setBrush(grad_r)
        painter.drawPolygon(right_poly)

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#495057"))
        painter.drawText(
            QRectF(4, 8, cx - 34, 18),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            self._max_node_txt,
        )
        painter.drawText(
            QRectF(cx + 32, 8, w - cx - 36, 18),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            self._max_edge_txt,
        )
        painter.drawText(
            QRectF(4, 66, cx - 20, 16),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            "low",
        )
        painter.drawText(
            QRectF(cx + 20, 66, w - cx - 24, 16),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            "low",
        )


def _disco_node_colors(
    ratio: float,
    mode: str,
) -> tuple[QColor, QColor, QColor, bool]:
    """Return (top_color, bottom_color, border_color, use_white_text) like Disco."""
    r = min(1.0, max(0.0, ratio))
    if mode == "performance":
        top = QColor(int(244 - r * 86), int(236 - r * 172), int(228 - r * 175))
        bot = QColor(int(228 - r * 92), int(214 - r * 168), int(202 - r * 165))
        bdr = QColor("#7D2626" if r > 0.5 else "#9E8775")
        return top, bot, bdr, r > 0.48

    # Exact Fluxicon Disco frequency stops (silver-gray -> slate blue -> teal -> Prussian blue)
    if r < 0.25:
        t = r / 0.25
        top = QColor(int(241 - t * 43), int(241 - t * 29), int(244 - t * 16))
        bot = QColor(int(220 - t * 50), int(222 - t * 32), int(228 - t * 14))
        bdr = QColor("#989EA6" if t < 0.5 else "#7D93AC")
        return top, bot, bdr, False
    if r < 0.60:
        t = (r - 0.25) / 0.35
        top = QColor(int(198 - t * 145), int(212 - t * 88), int(228 - t * 44))
        bot = QColor(int(170 - t * 135), int(190 - t * 86), int(214 - t * 54))
        bdr = QColor("#5B7898" if t < 0.4 else "#1A5988")
        return top, bot, bdr, t > 0.45
    t = (r - 0.60) / 0.40
    top = QColor(int(53 - t * 44), int(124 - t * 47), int(184 - t * 62))
    bot = QColor(int(35 - t * 30), int(104 - t * 48), int(160 - t * 69))
    bdr = QColor("#063556")
    return top, bot, bdr, True


class ProcessMapPage(QWidget):
    """Fluxicon Disco-style Process Map tab with Sugiyama layout."""

    NODE_W = 190.0
    NODE_H = 44.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.event_df: pd.DataFrame | None = None
        self._map_data: dict[str, Any] | None = None
        self._dirty = False
        self._mode = "frequency"
        self._search_text = ""

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(95)
        self._render_timer.timeout.connect(self._render_graph)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sub-toolbar
        subbar = QFrame()
        subbar.setObjectName("discoSubBar")
        sub_layout = QHBoxLayout(subbar)
        sub_layout.setContentsMargins(14, 5, 14, 5)
        sub_layout.setSpacing(10)

        sub_layout.addWidget(QLabel("Zoom"))
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(20, 220)
        self.slider_zoom.setValue(90)
        self.slider_zoom.setFixedWidth(150)
        self.slider_zoom.valueChanged.connect(self._on_zoom_slider)
        sub_layout.addWidget(self.slider_zoom)

        self.lbl_zoom = QLabel("90%")
        self.lbl_zoom.setFixedWidth(38)
        sub_layout.addWidget(self.lbl_zoom)

        btn_fit = QPushButton("Fit to Screen")
        btn_fit.setObjectName("toolbarBtn")
        btn_fit.clicked.connect(self._fit_view)
        sub_layout.addWidget(btn_fit)

        self.lbl_status = QLabel("Import an event log to discover the process map.")
        self.lbl_status.setStyleSheet("color: #5C646C;")
        sub_layout.addWidget(self.lbl_status, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(130)
        self.progress.setTextVisible(False)
        self.progress.hide()
        sub_layout.addWidget(self.progress)

        self.txt_search = make_disco_search("Search activity...")
        self.txt_search.setFixedWidth(210)
        self.txt_search.textChanged.connect(self._on_search_changed)
        sub_layout.addWidget(self.txt_search)

        root.addWidget(subbar)

        # Body: Graph Canvas (left) + Detail Control Sidebar (right)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.scene = QGraphicsScene(self)
        self.view = _ZoomableGraphView(self.scene, self)
        self.view.zoom_changed.connect(self._sync_zoom_slider)
        body.addWidget(self.view, 1)

        # Right-hand Disco Detail panel (Activities 100%, Paths 0% default!)
        side = QFrame()
        side.setObjectName("discoSideControlPanel")
        side.setFixedWidth(238)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(14, 12, 14, 12)
        side_layout.setSpacing(12)

        lbl_detail = QLabel("Detail")
        lbl_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_detail.setStyleSheet("font-size: 13px; font-weight: 700; color: #3A3F45;")
        side_layout.addWidget(lbl_detail)

        sliders_row = QHBoxLayout()
        sliders_row.setSpacing(16)

        act_col = QVBoxLayout()
        lbl_act_cap = QLabel("Activities")
        lbl_act_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_act_cap.setStyleSheet("font-weight: 600; color: #4A4F55;")
        self.slider_activities = QSlider(Qt.Orientation.Vertical)
        self.slider_activities.setRange(5, 100)
        self.slider_activities.setValue(100)
        self.slider_activities.setMinimumHeight(180)
        self.slider_activities.valueChanged.connect(self._on_detail_slider_changed)
        self.lbl_act_pct = QLabel("100%")
        self.lbl_act_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        act_col.addWidget(lbl_act_cap)
        act_col.addWidget(self.slider_activities, 1, Qt.AlignmentFlag.AlignHCenter)
        act_col.addWidget(self.lbl_act_pct)

        path_col = QVBoxLayout()
        lbl_path_cap = QLabel("Paths")
        lbl_path_cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_path_cap.setStyleSheet("font-weight: 600; color: #4A4F55;")
        self.slider_paths = QSlider(Qt.Orientation.Vertical)
        self.slider_paths.setRange(0, 100)
        self.slider_paths.setValue(0)  # Exact Disco default: 0% clean backbone!
        self.slider_paths.setMinimumHeight(180)
        self.slider_paths.valueChanged.connect(self._on_detail_slider_changed)
        self.lbl_path_pct = QLabel("0%")
        self.lbl_path_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path_col.addWidget(lbl_path_cap)
        path_col.addWidget(self.slider_paths, 1, Qt.AlignmentFlag.AlignHCenter)
        path_col.addWidget(self.lbl_path_pct)

        sliders_row.addLayout(act_col, 1)
        sliders_row.addLayout(path_col, 1)
        side_layout.addLayout(sliders_row, 1)

        self.mode_toggle = DiscoSegmentedToggle(
            [("frequency", "Frequency"), ("performance", "Performance")]
        )
        self.mode_toggle.changed.connect(self._on_mode_changed)
        side_layout.addWidget(self.mode_toggle, 0, Qt.AlignmentFlag.AlignHCenter)

        lbl_show = QLabel("Show:")
        lbl_show.setStyleSheet("font-weight: 600; color: #4A4F55;")
        side_layout.addWidget(lbl_show)

        self.combo_metric = QComboBox()
        self.combo_metric.addItems(["Absolute frequency", "Case frequency"])
        self.combo_metric.currentIndexChanged.connect(lambda _i: self._render_graph())
        side_layout.addWidget(self.combo_metric)

        self.legend_widget = _LegendRampWidget(side)
        side_layout.addWidget(self.legend_widget)

        body.addWidget(side)
        root.addLayout(body, 1)

    # ------------------------------------------------------------ public API
    def set_event_data(self, event_df: pd.DataFrame | None) -> None:
        self.event_df = event_df
        self._map_data = None
        self.scene.clear()

        if event_df is None or event_df.empty:
            self._dirty = False
            self.progress.hide()
            self.lbl_status.setText("Import an event log to discover the process map.")
            return

        self._dirty = True
        if self.isVisible():
            self.run_discovery()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty and self.event_df is not None and not self.event_df.empty:
            self.run_discovery()

    def run_discovery(self) -> None:
        if self.event_df is None or self.event_df.empty:
            return
        df_ref = self.event_df
        self._dirty = False
        self.progress.show()
        self.lbl_status.setText("Computing Directly-Follows Process Map…")

        GLOBAL_TASK_SCHEDULER.submit(
            "process_map",
            lambda: compute_process_map_data(df_ref),
            self._on_completed,
            self._on_failed,
            high_priority=True,
        )

    # ------------------------------------------------------------ slots
    def _on_completed(self, data: dict[str, Any]) -> None:
        self.progress.hide()
        self._map_data = data
        n_act = len(data.get("activities", {}))
        n_edges = len(data.get("edges", []))
        self.lbl_status.setText(
            f"Process Map  ·  {n_act:,} activities  ·  {n_edges:,} distinct transitions"
        )
        self._render_graph()
        self._fit_view()

    def _on_failed(self, msg: str) -> None:
        self.progress.hide()
        self.lbl_status.setText(f"Could not compute process map: {msg}")

    def _on_zoom_slider(self, val: int) -> None:
        self.lbl_zoom.setText(f"{val}%")
        self.view.set_zoom_percent(val)

    def _sync_zoom_slider(self, val: int) -> None:
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(val)
        self.slider_zoom.blockSignals(False)
        self.lbl_zoom.setText(f"{val}%")

    def _fit_view(self) -> None:
        rect = self.scene.itemsBoundingRect()
        if rect.isEmpty():
            return
        self.view.fitInView(
            rect.adjusted(-45, -35, 45, 35),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        scale_x = self.view.transform().m11()
        pct = max(20, min(220, int(round(scale_x * 100))))
        self._sync_zoom_slider(pct)
        self.view._zoom_pct = pct

    def _on_detail_slider_changed(self) -> None:
        self.lbl_act_pct.setText(f"{self.slider_activities.value()}%")
        self.lbl_path_pct.setText(f"{self.slider_paths.value()}%")
        self._render_timer.start()

    def _on_mode_changed(self, key: str) -> None:
        self._mode = key
        self.combo_metric.blockSignals(True)
        self.combo_metric.clear()
        if key == "performance":
            self.combo_metric.addItems(["Mean duration", "Total duration"])
        else:
            self.combo_metric.addItems(["Absolute frequency", "Case frequency"])
        self.combo_metric.blockSignals(False)
        self._render_graph()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self._render_timer.start()

    # ------------------------------------------------------------ rendering
    def _render_graph(self) -> None:
        self.scene.clear()
        if not self._map_data or not self._map_data.get("activities"):
            return

        activities: dict[str, dict[str, Any]] = self._map_data["activities"]
        all_edges: list[dict[str, Any]] = self._map_data["edges"]
        raw_start: dict[str, int] = self._map_data["start_edges"]
        raw_end: dict[str, int] = self._map_data["end_edges"]

        metric_text = self.combo_metric.currentText()
        use_case_freq = metric_text == "Case frequency"
        use_total_dur = metric_text == "Total duration"

        # 1. Filter top Activities %
        act_pct = self.slider_activities.value() / 100.0
        sorted_acts = sorted(
            activities.items(),
            key=lambda kv: (-kv[1]["abs_freq"], kv[0]),
        )
        keep_n = max(1, int(math.ceil(len(sorted_acts) * act_pct)))
        kept_acts = {name: meta for name, meta in sorted_acts[:keep_n]}

        start_edges = {k: v for k, v in raw_start.items() if k in kept_acts}
        end_edges = {k: v for k, v in raw_end.items() if k in kept_acts}

        # 2. Select clean Disco Spanning Backbone + Paths % transitions
        path_pct = self.slider_paths.value() / 100.0
        candidate_edges = [
            e for e in all_edges if e["src"] in kept_acts and e["dst"] in kept_acts
        ]
        non_self = [e for e in candidate_edges if e["src"] != e["dst"]]
        self_loops = [e for e in candidate_edges if e["src"] == e["dst"]]

        shown_edges = _select_disco_backbone_edges(
            kept_acts, non_self, start_edges, end_edges, path_pct
        )

        # Self-loops: at 0%, show major self-loops (>= 20% of activity volume); scale up with Paths %
        self_loops.sort(key=lambda e: -e["abs_freq"])
        major_loops = [
            e
            for e in self_loops
            if e["abs_freq"] >= 0.20 * kept_acts[e["src"]]["abs_freq"]
        ]
        minor_loops = [e for e in self_loops if e not in major_loops]
        shown_loops = major_loops + minor_loops[: int(round(len(minor_loops) * path_pct))]

        # Start & End dashed arrows: at 0%, show dominant entry/exit (>= 50% of max); scale up with Paths %
        def filter_terminals(term_map: dict[str, int]) -> list[tuple[str, int]]:
            if not term_map:
                return []
            ordered_t = sorted(term_map.items(), key=lambda kv: -kv[1])
            peak = ordered_t[0][1]
            dom = [kv for kv in ordered_t if kv[1] >= 0.50 * peak]
            rest = [kv for kv in ordered_t if kv[1] < 0.50 * peak]
            extra_t = int(round(len(rest) * (path_pct ** 1.25))) if path_pct > 0 else 0
            return dom + rest[:extra_t]

        shown_starts = filter_terminals(start_edges)
        shown_ends = filter_terminals(end_edges)

        # 3. Compute Sugiyama hierarchical layout
        positions, ranks, layers = _compute_sugiyama_layout(
            kept_acts,
            shown_edges,
            start_edges,
            end_edges,
            node_w=self.NODE_W,
        )

        # 4. Compute node & edge metric scales
        node_vals: dict[str, float] = {}
        if self._mode == "performance":
            for name in kept_acts:
                inc_durs = [
                    e["mean_sec"]
                    for e in candidate_edges
                    if e["dst"] == name and e["mean_sec"] is not None
                ]
                if use_total_dur:
                    tot_durs = [
                        e["total_sec"] for e in candidate_edges if e["dst"] == name
                    ]
                    node_vals[name] = float(sum(tot_durs))
                else:
                    node_vals[name] = (
                        float(sum(inc_durs) / len(inc_durs)) if inc_durs else 0.0
                    )
        else:
            for name, meta in kept_acts.items():
                node_vals[name] = float(
                    meta["case_freq"] if use_case_freq else meta["abs_freq"]
                )

        def edge_metric(edge: dict[str, Any]) -> float:
            if self._mode == "performance":
                if use_total_dur:
                    return float(edge.get("total_sec") or 0.0)
                return float(edge.get("mean_sec") or 0.0)
            return float(edge["case_freq"] if use_case_freq else edge["abs_freq"])

        max_node_val = max(node_vals.values(), default=1.0) or 1.0
        all_drawn_edges = shown_edges + shown_loops
        max_edge_val = max((edge_metric(e) for e in all_drawn_edges), default=1.0) or 1.0

        if self._mode == "performance":
            self.legend_widget.set_legend(
                "performance",
                format_human_duration(max_node_val),
                format_human_duration(max_edge_val),
            )
        else:
            self.legend_widget.set_legend(
                "frequency",
                f"{int(max_node_val):,}",
                f"{int(max_edge_val):,}",
            )

        # 5. Compute distributed top/bottom connection ports per node so arrows don't pile up
        out_ports: dict[tuple[str, str], float] = {}
        in_ports: dict[tuple[str, str], float] = {}
        by_src: dict[str, list[str]] = {a: [] for a in kept_acts}
        by_dst: dict[str, list[str]] = {a: [] for a in kept_acts}
        for e in shown_edges:
            by_src[e["src"]].append(e["dst"])
            by_dst[e["dst"]].append(e["src"])

        port_span = min(104.0, self.NODE_W * 0.56)
        for u, dst_list in by_src.items():
            dst_sorted = sorted(dst_list, key=lambda d: positions[d].x())
            k = len(dst_sorted)
            for idx, d in enumerate(dst_sorted):
                offset = 0.0 if k == 1 else -port_span / 2.0 + port_span * idx / (k - 1)
                out_ports[(u, d)] = offset

        for v, src_list in by_dst.items():
            src_sorted = sorted(src_list, key=lambda s: positions[s].x())
            k = len(src_sorted)
            for idx, s in enumerate(src_sorted):
                offset = 0.0 if k == 1 else -port_span / 2.0 + port_span * idx / (k - 1)
                in_ports[(s, v)] = offset

        shown_pair_set = {(e["src"], e["dst"]) for e in shown_edges}

        # 6. Draw Start & End dashed connectors
        for act_name, count in shown_starts:
            self._draw_terminal_edge(
                positions[START_NODE],
                positions[act_name],
                is_start=True,
                label_text=f"{count:,}" if self._mode == "frequency" else "",
            )

        for act_name, count in shown_ends:
            self._draw_terminal_edge(
                positions[act_name],
                positions[END_NODE],
                is_start=False,
                label_text=f"{count:,}" if self._mode == "frequency" else "",
            )

        # 7. Draw process edges (with bidirectional separation & obstacle-avoiding bypass)
        for edge in shown_edges:
            u, v = edge["src"], edge["dst"]
            val = edge_metric(edge)
            lbl = (
                format_human_duration(val)
                if self._mode == "performance"
                else f"{int(val):,}"
            )
            has_reverse = (v, u) in shown_pair_set
            self._draw_process_edge(
                u,
                v,
                positions=positions,
                ranks=ranks,
                layers=layers,
                out_offset=out_ports.get((u, v), 0.0),
                in_offset=in_ports.get((u, v), 0.0),
                weight_ratio=min(1.0, val / max_edge_val),
                label_text=lbl,
                has_reverse=has_reverse,
            )

        # 8. Draw teardrop self-loops
        for loop in shown_loops:
            val = edge_metric(loop)
            lbl = (
                format_human_duration(val)
                if self._mode == "performance"
                else f"{int(val):,}"
            )
            self._draw_self_loop(
                positions[loop["src"]],
                weight_ratio=min(1.0, val / max_edge_val),
                label_text=lbl,
            )

        # 9. Draw Start, End, and Activity boxes on top
        self._draw_terminal_circle(positions[START_NODE], is_start=True)
        self._draw_terminal_circle(positions[END_NODE], is_start=False)

        for act_name, pos in positions.items():
            if act_name in (START_NODE, END_NODE):
                continue
            val = node_vals.get(act_name, 0.0)
            ratio = min(1.0, max(0.0, val / max_node_val))
            sub_txt = (
                format_human_duration(val)
                if self._mode == "performance"
                else f"{int(val):,}"
            )
            matched = bool(self._search_text and self._search_text in act_name.lower())
            self._draw_activity_node(
                pos,
                act_name,
                sub_txt,
                ratio=ratio,
                highlighted=matched,
                meta=kept_acts[act_name],
            )

    def _draw_terminal_circle(self, center: QPointF, *, is_start: bool) -> None:
        r = 10.5
        if is_start:
            circle = self.scene.addEllipse(
                QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                QPen(QColor("#6E8F64"), 1.4),
                QBrush(QColor("#A3C499")),
            )
            circle.setZValue(10)
            tri = QPolygonF(
                [
                    QPointF(center.x() - 3.0, center.y() - 4.2),
                    QPointF(center.x() - 3.0, center.y() + 4.2),
                    QPointF(center.x() + 4.5, center.y()),
                ]
            )
            p_item = self.scene.addPolygon(
                tri, QPen(Qt.PenStyle.NoPen), QBrush(QColor("#FFFFFF"))
            )
            p_item.setZValue(11)
        else:
            # Disco concentric target stop symbol
            outer_c = self.scene.addEllipse(
                QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                QPen(QColor("#8E5B5B"), 1.6),
                QBrush(QColor("#D9B2B2")),
            )
            outer_c.setZValue(10)
            sq = self.scene.addRect(
                QRectF(center.x() - 4.0, center.y() - 4.0, 8.0, 8.0),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor("#7A4343")),
            )
            sq.setZValue(11)

    def _draw_terminal_edge(
        self,
        src: QPointF,
        dst: QPointF,
        *,
        is_start: bool,
        label_text: str,
    ) -> None:
        start_pt = QPointF(src.x(), src.y() + (11.0 if is_start else self.NODE_H / 2.0))
        end_pt = QPointF(dst.x(), dst.y() - (self.NODE_H / 2.0 if is_start else 11.0))

        dy = end_pt.y() - start_pt.y()
        path = QPainterPath(start_pt)
        path.cubicTo(
            QPointF(start_pt.x(), start_pt.y() + dy * 0.45),
            QPointF(end_pt.x(), end_pt.y() - dy * 0.45),
            end_pt,
        )
        color = QColor("#92AD7E") if is_start else QColor("#B98B82")
        pen = QPen(color, 1.35, Qt.PenStyle.DashLine)
        edge_item = QGraphicsPathItem(path)
        edge_item.setPen(pen)
        edge_item.setZValue(1)
        self.scene.addItem(edge_item)

        self._draw_arrowhead(path, end_pt, color, size=6.2)

        if label_text:
            mid = path.pointAtPercent(0.50)
            lbl = QGraphicsSimpleTextItem(label_text)
            lbl.setFont(QFont("Segoe UI", 7))
            lbl.setBrush(QColor("#7B8770" if is_start else "#94746E"))
            lbl.setPos(mid.x() + 7.0, mid.y() - 7.0)
            lbl.setZValue(5)
            self.scene.addItem(lbl)

    def _draw_process_edge(
        self,
        u: str,
        v: str,
        *,
        positions: dict[str, QPointF],
        ranks: dict[str, int],
        layers: list[list[str]],
        out_offset: float,
        in_offset: float,
        weight_ratio: float,
        label_text: str,
        has_reverse: bool,
    ) -> None:
        p_u = positions[u]
        p_v = positions[v]
        ru, rv = ranks[u], ranks[v]

        going_down = p_v.y() > p_u.y()
        same_rank = ru == rv

        if same_rank:
            # Horizontal neighbor arc
            go_right = p_v.x() > p_u.x()
            start_pt = QPointF(
                p_u.x() + (self.NODE_W / 2.0 if go_right else -self.NODE_W / 2.0),
                p_u.y() + (-6.0 if has_reverse and u < v else 6.0 if has_reverse else 0.0),
            )
            end_pt = QPointF(
                p_v.x() + (-self.NODE_W / 2.0 if go_right else self.NODE_W / 2.0),
                p_v.y() + (-6.0 if has_reverse and u < v else 6.0 if has_reverse else 0.0),
            )
            bow_y = -28.0 if (not has_reverse or u < v) else 28.0
            mid_x = (start_pt.x() + end_pt.x()) / 2.0
            c1 = QPointF(mid_x, start_pt.y() + bow_y)
            c2 = QPointF(mid_x, end_pt.y() + bow_y)
        elif going_down:
            bow_x = 0.0
            if has_reverse:
                bow_x = -24.0
                start_pt = QPointF(p_u.x() - 16.0, p_u.y() + self.NODE_H / 2.0)
                end_pt = QPointF(p_v.x() - 16.0, p_v.y() - self.NODE_H / 2.0)
            else:
                start_pt = QPointF(p_u.x() + out_offset * 0.55, p_u.y() + self.NODE_H / 2.0)
                end_pt = QPointF(p_v.x() + in_offset * 0.55, p_v.y() - self.NODE_H / 2.0)

            # Check if a multi-rank jump collides with intermediate boxes -> route cleanly around!
            if rv - ru >= 2:
                obstructed = False
                min_lyr_x = 0.0
                max_lyr_x = 0.0
                for r_mid in range(ru + 1, rv):
                    for mid_act in layers[r_mid]:
                        mx = positions[mid_act].x()
                        min_lyr_x = min(min_lyr_x, mx)
                        max_lyr_x = max(max_lyr_x, mx)
                        t = (r_mid - ru) / (rv - ru)
                        line_x = start_pt.x() + (end_pt.x() - start_pt.x()) * t
                        if abs(mx - line_x) < self.NODE_W * 0.62:
                            obstructed = True
                if obstructed:
                    # Route around whichever side (left or right) is closer
                    avg_x = (start_pt.x() + end_pt.x()) / 2.0
                    if avg_x <= 0:
                        corridor_x = min(start_pt.x(), end_pt.x(), min_lyr_x) - self.NODE_W * 0.78
                        start_pt = QPointF(p_u.x() - self.NODE_W * 0.34, p_u.y() + self.NODE_H / 2.0)
                        end_pt = QPointF(p_v.x() - self.NODE_W * 0.34, p_v.y() - self.NODE_H / 2.0)
                    else:
                        corridor_x = max(start_pt.x(), end_pt.x(), max_lyr_x) + self.NODE_W * 0.78
                        start_pt = QPointF(p_u.x() + self.NODE_W * 0.34, p_u.y() + self.NODE_H / 2.0)
                        end_pt = QPointF(p_v.x() + self.NODE_W * 0.34, p_v.y() - self.NODE_H / 2.0)
                    dy = end_pt.y() - start_pt.y()
                    c1 = QPointF(corridor_x, start_pt.y() + dy * 0.25)
                    c2 = QPointF(corridor_x, end_pt.y() - dy * 0.25)
                else:
                    dy = end_pt.y() - start_pt.y()
                    c1 = QPointF(start_pt.x() + bow_x, start_pt.y() + dy * 0.42)
                    c2 = QPointF(end_pt.x() + bow_x, end_pt.y() - dy * 0.42)
            else:
                dy = end_pt.y() - start_pt.y()
                c1 = QPointF(start_pt.x() + bow_x, start_pt.y() + dy * 0.42)
                c2 = QPointF(end_pt.x() + bow_x, end_pt.y() - dy * 0.42)
        else:
            # Upward feedback / rework edge
            if has_reverse and ru - rv == 1:
                # Adjacent bidirectional pair (like W_Complete <-> A_Concept!): tight right-hand lens arc
                start_pt = QPointF(p_u.x() + 18.0, p_u.y() - self.NODE_H / 2.0)
                end_pt = QPointF(p_v.x() + 18.0, p_v.y() + self.NODE_H / 2.0)
                dy = start_pt.y() - end_pt.y()
                c1 = QPointF(start_pt.x() + 28.0, start_pt.y() - dy * 0.42)
                c2 = QPointF(end_pt.x() + 28.0, end_pt.y() + dy * 0.42)
            else:
                # Longer upward loop: curve gracefully around outer side
                go_right = p_u.x() >= p_v.x()
                side_sign = 1.0 if go_right else -1.0
                start_pt = QPointF(
                    p_u.x() + side_sign * (self.NODE_W * 0.36),
                    p_u.y() - self.NODE_H / 2.0,
                )
                end_pt = QPointF(
                    p_v.x() + side_sign * (self.NODE_W * 0.36),
                    p_v.y() + self.NODE_H / 2.0,
                )
                span_ranks = max(1, ru - rv)
                bow = side_sign * (55.0 + min(110.0, span_ranks * 22.0))
                dy = start_pt.y() - end_pt.y()
                c1 = QPointF(start_pt.x() + bow, start_pt.y() - dy * 0.28)
                c2 = QPointF(end_pt.x() + bow, end_pt.y() + dy * 0.28)

        path = QPainterPath(start_pt)
        path.cubicTo(c1, c2, end_pt)

        # Disco stroke color & thickness scaled smoothly by weight
        gray_v = int(126 - weight_ratio * 88)
        edge_color = QColor(gray_v, gray_v + 3, gray_v + 8)
        stroke_w = 1.15 + weight_ratio * 4.0

        edge_item = QGraphicsPathItem(path)
        edge_item.setPen(QPen(edge_color, stroke_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        edge_item.setZValue(2)
        self.scene.addItem(edge_item)

        self._draw_arrowhead(path, end_pt, edge_color, size=6.6 + weight_ratio * 2.2)

        if label_text:
            t_pos = 0.46 if not has_reverse else (0.44 if going_down else 0.56)
            mid = path.pointAtPercent(t_pos)
            lbl = QGraphicsSimpleTextItem(label_text)
            lbl_font = QFont("Segoe UI", 7)
            lbl.setFont(lbl_font)
            lbl.setBrush(QColor("#383E45"))
            br = lbl.boundingRect()

            # Offset bidirectional labels outward from each other so they never collide
            lx = mid.x() - br.width() / 2.0
            if has_reverse and abs(ru - rv) == 1:
                lx = (mid.x() - br.width() - 5.0) if going_down else (mid.x() + 5.0)
            elif abs(start_pt.x() - end_pt.x()) < 8.0 and not has_reverse:
                lx = mid.x() + 6.0

            ly = mid.y() - br.height() / 2.0
            halo = self.scene.addRect(
                QRectF(lx - 2.5, ly - 0.5, br.width() + 5.0, br.height() + 1.0),
                QPen(Qt.PenStyle.NoPen),
                QBrush(QColor(255, 255, 255, 220)),
            )
            halo.setZValue(4)
            lbl.setPos(lx, ly)
            lbl.setZValue(5)
            self.scene.addItem(lbl)

    def _draw_arrowhead(
        self,
        path: QPainterPath,
        end_pt: QPointF,
        color: QColor,
        *,
        size: float = 7.0,
    ) -> None:
        t_near = path.pointAtPercent(0.93)
        angle = math.atan2(end_pt.y() - t_near.y(), end_pt.x() - t_near.x())
        p1 = QPointF(
            end_pt.x() - size * math.cos(angle - 0.46),
            end_pt.y() - size * math.sin(angle - 0.46),
        )
        p2 = QPointF(
            end_pt.x() - size * math.cos(angle + 0.46),
            end_pt.y() - size * math.sin(angle + 0.46),
        )
        head = self.scene.addPolygon(
            QPolygonF([end_pt, p1, p2]),
            QPen(Qt.PenStyle.NoPen),
            QBrush(color),
        )
        head.setZValue(3)

    def _draw_self_loop(
        self,
        center: QPointF,
        *,
        weight_ratio: float,
        label_text: str,
    ) -> None:
        right_x = center.x() + self.NODE_W / 2.0
        p_start = QPointF(right_x, center.y() - 8.5)
        p_end = QPointF(right_x, center.y() + 8.5)
        path = QPainterPath(p_start)
        path.cubicTo(
            QPointF(right_x + 38.0, center.y() - 22.0),
            QPointF(right_x + 38.0, center.y() + 22.0),
            p_end,
        )
        gray_v = int(115 - weight_ratio * 85)
        color = QColor(gray_v, gray_v + 3, gray_v + 8)
        stroke_w = 1.2 + weight_ratio * 4.2
        item = QGraphicsPathItem(path)
        item.setPen(QPen(color, stroke_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        item.setZValue(3)
        self.scene.addItem(item)

        self._draw_arrowhead(path, p_end, color, size=6.2 + weight_ratio * 1.8)

        if label_text:
            lbl = QGraphicsSimpleTextItem(label_text)
            lbl.setFont(QFont("Segoe UI", 7))
            lbl.setBrush(QColor("#383E45"))
            lbl.setPos(right_x + 33.0, center.y() - 7.0)
            lbl.setZValue(5)
            self.scene.addItem(lbl)

    def _draw_activity_node(
        self,
        center: QPointF,
        name: str,
        subtitle: str,
        *,
        ratio: float,
        highlighted: bool,
        meta: dict[str, Any],
    ) -> None:
        rect = QRectF(
            center.x() - self.NODE_W / 2.0,
            center.y() - self.NODE_H / 2.0,
            self.NODE_W,
            self.NODE_H,
        )

        # Subtle Disco drop shadow
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(rect.translated(0.0, 2.0), 5.0, 5.0)
        sh_item = QGraphicsPathItem(shadow_path)
        sh_item.setPen(Qt.PenStyle.NoPen)
        sh_item.setBrush(QColor(0, 0, 0, 24))
        sh_item.setZValue(9)
        self.scene.addItem(sh_item)

        top_c, bot_c, border_c, white_txt = _disco_node_colors(ratio, self._mode)
        if highlighted:
            border_c = QColor("#E59B14")

        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, top_c)
        grad.setColorAt(1.0, bot_c)

        path = QPainterPath()
        path.addRoundedRect(rect, 5.0, 5.0)
        item = QGraphicsPathItem(path)
        item.setPen(QPen(border_c, 2.6 if highlighted else 1.15))
        item.setBrush(QBrush(grad))
        item.setZValue(10)
        item.setToolTip(
            f"{name}\n"
            f"Absolute events: {meta['abs_freq']:,}\n"
            f"Unique cases: {meta['case_freq']:,}"
        )
        self.scene.addItem(item)

        fg_main = QColor("#FFFFFF") if white_txt else QColor("#1D2126")
        fg_sub = QColor("#DCEAF7") if white_txt else QColor("#495058")

        title_font = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        fm = QFontMetrics(title_font)
        elided = fm.elidedText(name, Qt.TextElideMode.ElideRight, int(self.NODE_W - 16))

        t_item = QGraphicsSimpleTextItem(elided)
        t_item.setFont(title_font)
        t_item.setBrush(fg_main)
        t_br = t_item.boundingRect()
        t_item.setPos(center.x() - t_br.width() / 2.0, rect.top() + 6.5)
        t_item.setZValue(11)
        self.scene.addItem(t_item)

        sub_font = QFont("Segoe UI", 7)
        s_item = QGraphicsSimpleTextItem(subtitle)
        s_item.setFont(sub_font)
        s_item.setBrush(fg_sub)
        s_br = s_item.boundingRect()
        s_item.setPos(center.x() - s_br.width() / 2.0, rect.top() + 23.0)
        s_item.setZValue(11)
        self.scene.addItem(s_item)


__all__ = ["ProcessMapPage", "compute_process_map_data"]
