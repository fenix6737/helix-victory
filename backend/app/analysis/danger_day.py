"""危険日判定 — 当たり予測より回避を優先"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

import pandas as pd

from app.analysis.engine import StoreMode, detect_store_mode


class DangerLevel(str, Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGER = "danger"
    CRITICAL = "critical"


@dataclass
class DangerAssessment:
    level: DangerLevel
    score: float  # 0=安全, 100=危険
    should_play: bool
    headline: str
    reasons: list[str]
    store_mode: str

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "score": round(self.score, 1),
            "should_play": self.should_play,
            "headline": self.headline,
            "reasons": self.reasons,
            "store_mode": self.store_mode,
        }


def assess_danger_day(
    df: pd.DataFrame,
    target_date: date,
    event_days: list[int] | None = None,
) -> DangerAssessment:
    """
    店舗全体の危険度を評価。
    回収モード・放出翌日・稼働異常・島弱化・特定日不一致を検出。
    """
    reasons: list[str] = []
    risk = 0.0

    if df.empty:
        return DangerAssessment(
            level=DangerLevel.CAUTION,
            score=50.0,
            should_play=False,
            headline="データ不足 — 本日は様子見推奨",
            reasons=["・収集ログが不足しています"],
            store_mode="unknown",
        )

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    store_mode = detect_store_mode(df, target_date, event_days)
    mode_val = store_mode.value

    recent = df[df["captured_at"].dt.date >= target_date - timedelta(days=5)]
    if not recent.empty:
        daily_mean = recent.groupby(recent["captured_at"].dt.date)["diff_coins"].mean()
        if len(daily_mean) >= 2:
            trend = float(daily_mean.iloc[-1] - daily_mean.iloc[0])
            if trend < -400:
                risk += 28
                reasons.append("・直近5日で店舗全体が回収傾向")
            if trend > 500:
                risk += 18
                reasons.append("・直近で強い放出 — 翌日は凹みやすい")

    if store_mode == StoreMode.RECOVERY:
        risk += 35
        reasons.append("・回収モード検出 — 据え置き・回収が続きやすい")
    elif store_mode == StoreMode.RELEASE:
        risk += 22
        reasons.append("・放出モード — 翌営業日は慎重に")

    ops = recent["is_operating"].dropna() if "is_operating" in recent.columns else pd.Series(dtype=float)
    if len(ops) > 20 and float(ops.mean()) < 0.35:
        risk += 20
        reasons.append("・稼働率が異常に低い")

    last_day = df[df["captured_at"].dt.date == target_date - timedelta(days=1)]
    if not last_day.empty:
        y_mean = float(last_day["diff_coins"].dropna().mean()) if last_day["diff_coins"].notna().any() else 0.0
        if y_mean > 800:
            risk += 15
            reasons.append("・前日は店舗全体が強プラス（放出翌日リスク）")

    ev_days = event_days or [3, 9]
    dom = target_date.day
    if dom not in ev_days and (dom % 10) not in ev_days:
        wd = target_date.weekday()
        hist = df[df["captured_at"].dt.weekday == wd]
        if len(hist) >= 30:
            dmean = hist.groupby(hist["captured_at"].dt.date)["diff_coins"].mean()
            if len(dmean) >= 5 and float(dmean.mean()) < -200:
                risk += 12
                reasons.append("・本日の曜日は過去に弱い傾向")

    if "island_id" in df.columns:
        recent3 = df[df["captured_at"].dt.date >= target_date - timedelta(days=3)]
        if not recent3.empty and recent3["island_id"].notna().any():
            island_avg = (
                recent3.groupby("island_id")["diff_coins"].mean().dropna()
            )
            if len(island_avg) >= 3 and float(island_avg.mean()) < -350:
                risk += 14
                reasons.append("・島単位で全体弱化")

    risk = min(100.0, risk)
    if risk >= 55:
        level = DangerLevel.DANGER
        headline = "今日は危険 — 打たない判断も最適"
        should_play = False
    elif risk >= 30:
        level = DangerLevel.CAUTION
        headline = "要注意 — 厳選台のみ"
        should_play = True
    else:
        level = DangerLevel.SAFE
        headline = "通常営業想定 — 推奨台を優先"
        should_play = True

    if not reasons:
        reasons.append("・重大な危険シグナルは未検出")

    return DangerAssessment(
        level=level,
        score=risk,
        should_play=should_play,
        headline=headline,
        reasons=reasons[:6],
        store_mode=mode_val,
    )
