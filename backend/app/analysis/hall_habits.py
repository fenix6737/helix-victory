"""
店舗クセ — イベント日の末尾・島ブロック別の過去配分傾向
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


def _is_event_day(d: date, event_days: list[int]) -> bool:
    return d.day in event_days or (d.day % 10) in event_days


@dataclass
class HallHabitCache:
    """analyze_store 1回あたり1度だけ構築するキャッシュ"""

    tail_avg: dict[int, float]
    island_avg: dict[str, float]
    block_avg: dict[int, float]


def build_hall_habit_cache(
    df: pd.DataFrame,
    target_date: date,
    event_days: list[int] | None = None,
) -> HallHabitCache:
    ev_days = event_days or [3, 9]
    empty = HallHabitCache(tail_avg={}, island_avg={}, block_avg={})
    if df.empty:
        return empty

    work = df.copy()
    work["captured_at"] = pd.to_datetime(work["captured_at"], utc=True)
    work["day"] = work["captured_at"].dt.date

    since = target_date - timedelta(days=90)
    ev_dates = sorted(
        {d for d in work["day"].unique() if since <= d < target_date and _is_event_day(d, ev_days)}
    )
    if len(ev_dates) < 2:
        return empty

    tail_avgs: dict[int, list[float]] = {}
    island_avgs: dict[str, list[float]] = {}
    block_avgs: dict[int, list[float]] = {}

    for ev_d in ev_dates[-3:]:
        day_df = work[work["day"] == ev_d]
        if day_df.empty:
            continue

        daily = day_df.groupby("machine_number")["diff_coins"].last()
        for mn, diff in daily.items():
            if pd.isna(diff):
                continue
            tail = int(mn) % 10
            tail_avgs.setdefault(tail, []).append(float(diff))
            block = (int(mn) // 100) * 100
            block_avgs.setdefault(block, []).append(float(diff))

        if "island_id" in day_df.columns:
            for isl, grp in day_df.groupby(day_df["island_id"].astype(str)):
                if not isl or isl == "nan":
                    continue
                m = grp.groupby("machine_number")["diff_coins"].last().mean()
                if pd.notna(m):
                    island_avgs.setdefault(isl, []).append(float(m))

    return HallHabitCache(
        tail_avg={k: sum(v) / len(v) for k, v in tail_avgs.items()},
        island_avg={k: sum(v) / len(v) for k, v in island_avgs.items()},
        block_avg={k: sum(v) / len(v) for k, v in block_avgs.items()},
    )


def _score_from_avg(avg: float, strong: float, mild: float) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if avg > strong:
        return 0.45, [f"・イベント日 平均+{avg:.0f}枚"]
    if avg > mild:
        return 0.25, ["・イベント日 やや強め"]
    if avg > 0:
        return 0.12, []
    return 0.0, []


def lookup_hall_habit_scores(
    cache: HallHabitCache | None,
    machine_number: int,
    island_id: str | None,
) -> tuple[float, list[str]]:
    if not cache:
        return 0.0, []

    score = 0.0
    reasons: list[str] = []
    tail = machine_number % 10

    if tail in cache.tail_avg:
        part, rs = _score_from_avg(cache.tail_avg[tail], 300, 0)
        if part:
            score += part
            reasons.append(f"・イベント日末尾{tail}番" + (rs[0].replace("・イベント日 ", "") if rs else ""))

    isl_key = str(island_id) if island_id and pd.notna(island_id) else None
    avg_isl: float | None = None
    if isl_key and isl_key in cache.island_avg:
        avg_isl = cache.island_avg[isl_key]
    else:
        block = (machine_number // 100) * 100
        if block in cache.block_avg:
            avg_isl = cache.block_avg[block]

    if avg_isl is not None:
        if avg_isl > 400:
            score += 0.4
            reasons.append(f"・強い島/ブロック 平均+{avg_isl:.0f}枚")
        elif avg_isl > 0:
            score += 0.2
            reasons.append("・島ブロックややプラス傾向")

    return min(1.0, score), reasons


def compute_hall_habit_scores(
    df: pd.DataFrame,
    store_id: str,
    machine_number: int,
    island_id: str | None,
    target_date: date,
    event_days: list[int] | None = None,
) -> tuple[float, list[str]]:
    """後方互換 — 単体テスト用。本番は build_hall_habit_cache + lookup を使用。"""
    cache = build_hall_habit_cache(df, target_date, event_days)
    return lookup_hall_habit_scores(cache, machine_number, island_id)
