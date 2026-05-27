"""
ガチ期待値 — ボーダー・回転率逆算・店舗クセ
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.analysis.hall_habits import HallHabitCache, lookup_hall_habit_scores
from app.analysis.machine_borders import (
    BorderSpec,
    border_exceed_score,
    estimate_rotation_per_1000_yen,
    match_border,
)
from app.analysis.graph_intraday import parse_graph_samples, refine_rotation_from_intraday
from app.featured import classify_featured

DEFAULT_SLOT_BORDER = 21.0
DEFAULT_PACHI_BORDER = 16.5


def _diff_trend(g: pd.DataFrame) -> float:
    daily = (
        g.groupby(g["captured_at"].dt.date)["diff_coins"]
        .last()
        .dropna()
        .sort_index()
    )
    if len(daily) < 2:
        return 0.0
    return float(daily.iloc[-1] - daily.iloc[0])


def border_ev_score(
    g: pd.DataFrame,
    machine_number: int,
    title: str,
    game_type: str,
    target_date: date,
    store_metadata: dict | None,
    border_specs: list[BorderSpec] | None,
    habit_cache: HallHabitCache | None = None,
    island_id: str | None = None,
) -> tuple[float, list[str], float | None, bool]:
    """
    Returns: score 0-1, reasons, rot_per_1000_yen, border_exceeded (+1回転以上)
    """
    reasons: list[str] = []
    meta = store_metadata or {}
    specs = border_specs or []
    score = 0.0
    rot_per_k: float | None = None
    exceeded = False

    spec = match_border(title, specs)
    border_k = spec.border_per_1000_yen if spec else (
        DEFAULT_PACHI_BORDER if game_type == "pachinko" else DEFAULT_SLOT_BORDER
    )

    rot_series = g["rotation_count"].dropna() if "rotation_count" in g.columns else pd.Series(dtype=float)
    fg_series = g["final_games"].dropna() if "final_games" in g.columns else pd.Series(dtype=float)
    total_rot = float(rot_series.mean()) if rot_series.notna().any() else None
    fg_mean = float(fg_series.mean()) if fg_series.notna().any() else None

    if spec and total_rot:
        trend = _diff_trend(g)
        rot_per_k, invest = estimate_rotation_per_1000_yen(total_rot, fg_mean, spec, trend)
        if "graph_samples_json" in g.columns:
            gs_raw = g["graph_samples_json"].dropna()
            if not gs_raw.empty:
                samples = parse_graph_samples(gs_raw.iloc[-1])
                if samples:
                    rot_adj, _ = refine_rotation_from_intraday(
                        samples, total_rot, fg_mean, spec, trend
                    )
                    if rot_adj is not None:
                        rot_per_k = rot_adj
        if rot_per_k is not None:
            part, exceeded = border_exceed_score(rot_per_k, border_k, margin=1.0)
            score += 0.55 * part
            reasons.append(
                f"・推定{rot_per_k:.1f}回/k（ボーダー{border_k:.1f}）"
                + (" ★超え" if exceeded else "")
            )
    elif game_type == "slot" and fg_mean and fg_mean >= 100:
        rot_per_k = 25000.0 / max(fg_mean, 100) * (1000 / 250)
        part, exceeded = border_exceed_score(rot_per_k / 4, border_k, margin=1.0)
        score += 0.35 * part

    habit, habit_reasons = lookup_hall_habit_scores(
        habit_cache, machine_number, island_id, game_type=game_type
    )
    score += 0.35 * habit
    reasons.extend(habit_reasons)

    feat, _, _ = classify_featured(title)
    if feat:
        score += 0.1
        reasons.append("・看板機種")

    return min(1.0, score), reasons[:5], rot_per_k, exceeded
