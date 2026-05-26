"""異常検知 — 暴走時は推奨停止"""

from __future__ import annotations

import pandas as pd


def detect_anomalies(
    scored: list[dict],
    df: pd.DataFrame,
    integrity: dict,
) -> dict:
    alerts: list[str] = []
    block_recommendations = False
    severity = "ok"

    if not integrity.get("allow_analysis", True):
        return {
            "severity": "critical",
            "block_recommendations": True,
            "alerts": ["整合性監査失敗 — 推奨停止"],
        }

    recs = [s for s in scored if s.get("tier") == "recommend"]
    if len(recs) == 0 and len(scored) > 10:
        alerts.append("推奨0件 — 全滅または閾値異常")
        severity = "warning"

    if recs:
        scores = [s["score"] for s in recs]
        if max(scores) > 99 and min(scores) > 95:
            alerts.append("推奨スコアが異常に高い — 暴走の疑い")
            block_recommendations = True
            severity = "critical"
        if len(set(round(s, 0) for s in scores)) <= 2 and len(recs) >= 10:
            alerts.append("推奨スコアの偏り — 特徴量崩壊の疑い")
            severity = "warning"

    if not df.empty and "diff_coins" in df.columns:
        recent = df.tail(min(500, len(df)))
        if recent["diff_coins"].notna().all() and recent["diff_coins"].std() == 0:
            alerts.append("差枚が一定 — 波形破損の疑い")

    if len(recs) > 25:
        alerts.append(f"推奨過多 {len(recs)}件")

    return {
        "severity": severity,
        "block_recommendations": block_recommendations,
        "alerts": alerts,
        "recommend_count": len(recs),
    }
