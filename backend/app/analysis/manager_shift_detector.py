"""店長変更検知 — 営業癖の死を検知"""

from __future__ import annotations

import pandas as pd

from app.analysis.drift_detection import detect_feature_drift


def detect_manager_shift(
    historical_df: pd.DataFrame,
    recent_df: pd.DataFrame,
    prior_audit: dict | None = None,
) -> dict:
    drift = detect_feature_drift(historical_df, recent_df, prior_audit)
    score = float(drift.get("drift_score", 0))
    alerts = list(drift.get("alerts", []))

    hist = historical_df.copy()
    rec = recent_df.copy()
    if not hist.empty and not rec.empty:
        hist["captured_at"] = pd.to_datetime(hist["captured_at"], utc=True)
        rec["captured_at"] = pd.to_datetime(rec["captured_at"], utc=True)

        if "island_id" in hist.columns:
            h_layout = set(hist.groupby("island_id")["machine_id"].nunique().head(5).index.astype(str))
            r_layout = set(rec.groupby("island_id")["machine_id"].nunique().head(5).index.astype(str))
            if h_layout and r_layout and len(h_layout & r_layout) < len(h_layout) * 0.5:
                score = min(1.0, score + 0.25)
                alerts.append("島構成の入れ替わり — 配置変更の疑い")

        h_dom = hist["captured_at"].dt.day.value_counts().head(3).index.tolist()
        r_dom = rec["captured_at"].dt.day.value_counts().head(3).index.tolist()
        if h_dom and r_dom and h_dom[0] != r_dom[0]:
            score = min(1.0, score + 0.15)
            alerts.append("特定日パターン変化")

    if score >= 0.55:
        drift_level = "high"
        trust_decay = round(0.35 + score * 0.4, 2)
    elif score >= 0.3:
        drift_level = "medium"
        trust_decay = round(0.15 + score * 0.3, 2)
    else:
        drift_level = "low"
        trust_decay = round(score * 0.2, 2)

    return {
        "drift_level": drift_level,
        "operation_change_probability": round(min(0.99, score * 1.1), 3),
        "trust_decay": trust_decay,
        "alerts": alerts,
        "ui_warning": "営業変化検知：過去傾向の信頼性低下" if score >= 0.35 else None,
    }
