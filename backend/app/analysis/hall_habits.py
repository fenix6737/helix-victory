"""
店舗クセ — イベント日の末尾・島ブロック別の過去配分傾向
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def _is_event_day(d: date, event_days: list[int]) -> bool:
    return d.day in event_days or (d.day % 10) in event_days


def compute_hall_habit_scores(
    df: pd.DataFrame,
    store_id: str,
    machine_number: int,
    island_id: str | None,
    target_date: date,
    event_days: list[int] | None = None,
) -> tuple[float, list[str]]:
    """
    0〜1 のクセスコア。直近イベント日の末尾・島平均差枚がプラスなら加点。
    """
    ev_days = event_days or [3, 9]
    if df.empty:
        return 0.0, []

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    df["day"] = df["captured_at"].dt.date

    reasons: list[str] = []
    score = 0.0
    tail = machine_number % 10

    # 過去90日のイベント日のみ
    since = target_date - timedelta(days=90)
    ev_dates = sorted(
        {d for d in df["day"].unique() if since <= d < target_date and _is_event_day(d, ev_days)}
    )
    if len(ev_dates) < 2:
        return 0.0, []

    # 末尾別 — 直近3イベント日
    tail_scores: list[float] = []
    for ev_d in ev_dates[-3:]:
        day_df = df[df["day"] == ev_d]
        tail_m = day_df[day_df["machine_number"] % 10 == tail]
        if tail_m.empty:
            continue
        daily = tail_m.groupby("machine_number")["diff_coins"].last().mean()
        if pd.notna(daily):
            tail_scores.append(float(daily))

    if tail_scores:
        avg_tail = sum(tail_scores) / len(tail_scores)
        if avg_tail > 300:
            score += 0.45
            reasons.append(f"・イベント日末尾{tail}番 平均+{avg_tail:.0f}枚")
        elif avg_tail > 0:
            score += 0.25
            reasons.append(f"・イベント日末尾{tail}番 やや強め")

    # 島ブロック（500台単位など）
    if island_id and pd.notna(island_id):
        island_scores: list[float] = []
        block = str(island_id)
        for ev_d in ev_dates[-3:]:
            day_df = df[df["day"] == ev_d]
            if "island_id" in day_df.columns:
                isl = day_df[day_df["island_id"].astype(str) == block]
            else:
                isl = pd.DataFrame()
            if isl.empty:
                # machine_number ブロック代理
                block_num = (machine_number // 100) * 100
                isl = day_df[
                    (day_df["machine_number"] >= block_num)
                    & (day_df["machine_number"] < block_num + 100)
                ]
            if isl.empty:
                continue
            daily = isl.groupby("machine_number")["diff_coins"].last().mean()
            if pd.notna(daily):
                island_scores.append(float(daily))
        if island_scores:
            avg_isl = sum(island_scores) / len(island_scores)
            if avg_isl > 400:
                score += 0.4
                reasons.append(f"・強い島/ブロック 平均+{avg_isl:.0f}枚")
            elif avg_isl > 0:
                score += 0.2
                reasons.append("・島ブロックややプラス傾向")

    return min(1.0, score), reasons
