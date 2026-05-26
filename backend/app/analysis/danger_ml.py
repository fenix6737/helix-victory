"""危険日AI v2 — safe / caution / danger / critical"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.analysis.danger_day import DangerAssessment, DangerLevel, assess_danger_day


def score_danger_ml(
    df: pd.DataFrame,
    target_date: date,
    event_days: list[int] | None = None,
    drift_score: float = 0.0,
) -> DangerAssessment:
    base = assess_danger_day(df, target_date, event_days)
    if df.empty:
        return base

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    risk = base.score
    reasons = list(base.reasons)

    recent5 = df[df["captured_at"].dt.date >= target_date - timedelta(days=5)]
    if not recent5.empty:
        daily = recent5.groupby(recent5["captured_at"].dt.date)["diff_coins"].mean()
        if len(daily) >= 2:
            if float(daily.iloc[-1]) < -500:
                risk += 12
                reasons.append("・島全沈み/平均急落")
            if float(daily.iloc[-1]) > 600 and len(daily) >= 3:
                risk += 10
                reasons.append("・放出翌日リスク")

    yesterday = df[df["captured_at"].dt.date == target_date - timedelta(days=1)]
    if not yesterday.empty:
        ymean = float(yesterday["diff_coins"].dropna().mean())
        if ymean > 700:
            risk += 14
            reasons.append("・前日大放出")

    if target_date.day >= 28:
        risk += 8
        reasons.append("・月末")

    if "island_id" in df.columns:
        r3 = df[df["captured_at"].dt.date >= target_date - timedelta(days=3)]
        if not r3.empty:
            island_mean = r3.groupby("island_id")["diff_coins"].mean()
            if len(island_mean) >= 2 and float(island_mean.min()) < -600:
                risk += 11

    ops = recent5["is_operating"].dropna() if not recent5.empty else pd.Series(dtype=float)
    if len(ops) > 30:
        recent_ops = float(ops.tail(len(ops) // 2).mean())
        older_ops = float(ops.head(len(ops) // 2).mean())
        if older_ops - recent_ops > 0.25:
            risk += 13
            reasons.append("・稼働急落")

    if base.store_mode == "recovery":
        risk += 6

    fake_count = 0
    if len(recent5) > 50:
        for mid in recent5["machine_id"].unique()[:40]:
            mg = recent5[recent5["machine_id"] == mid].sort_values("captured_at")
            diffs = mg["diff_coins"].dropna().astype(float).tolist()
            if len(diffs) >= 4:
                from app.analysis.waveform_ml import analyze_waveform_series

                w = analyze_waveform_series(diffs)
                if w.get("fake_release") or w.get("ml_class") == "fake_release":
                    fake_count += 1
        if fake_count >= 3:
            risk += 16
            reasons.append("・fake_release多発")

    if drift_score >= 0.65:
        risk += 10
        reasons.append("・drift急変")

    risk = min(100.0, risk)
    level = DangerLevel.SAFE
    should_play = True
    headline = base.headline

    if risk >= 72:
        level = DangerLevel.CRITICAL
        should_play = False
        headline = "critical — 本日は行かない"
        reasons.insert(0, "・critical: 複合危険シグナル")
    elif risk >= 58:
        level = DangerLevel.DANGER
        should_play = False
        headline = "危険 — 打たない最適"
    elif risk >= 32:
        level = DangerLevel.CAUTION
        headline = "要注意 — 厳選台のみ"
    else:
        level = DangerLevel.SAFE

    return DangerAssessment(
        level=level,
        score=risk,
        should_play=should_play,
        headline=headline,
        reasons=reasons[:10],
        store_mode=base.store_mode,
    )
