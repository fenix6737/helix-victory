"""drift検知 v3 — 配置・島・稼働導線の変化 + 重み再編"""

from __future__ import annotations

import pandas as pd


def detect_feature_drift(
    historical_df: pd.DataFrame,
    recent_df: pd.DataFrame,
    prior_audit: dict | None = None,
) -> dict:
    alerts: list[str] = []
    drift_score = 0.0
    drift_types: list[str] = []

    if historical_df.empty or recent_df.empty:
        return {
            "drift_score": 0.0,
            "alerts": [],
            "signals": {},
            "historical_weight": 1.0,
            "recent_weight": 1.0,
            "historical_weight_decay": 1.0,
            "prefer_recent": False,
            "stop_legacy_features": False,
            "ev_confidence_penalty": 0.0,
            "drift_types": [],
        }

    hist = historical_df.copy()
    rec = recent_df.copy()
    hist["captured_at"] = pd.to_datetime(hist["captured_at"], utc=True)
    rec["captured_at"] = pd.to_datetime(rec["captured_at"], utc=True)

    h_mean = float(hist["diff_coins"].dropna().mean()) if hist["diff_coins"].notna().any() else 0.0
    r_mean = float(rec["diff_coins"].dropna().mean()) if rec["diff_coins"].notna().any() else 0.0
    mean_shift = abs(r_mean - h_mean)
    if mean_shift > 350:
        drift_score += 0.3
        drift_types.append("layout_shift")
        alerts.append("配置/平均差枚の急変")

    h_ops = float(hist["is_operating"].mean()) if hist["is_operating"].notna().any() else 0.5
    r_ops = float(rec["is_operating"].mean()) if rec["is_operating"].notna().any() else 0.5
    if abs(r_ops - h_ops) > 0.2:
        drift_score += 0.22
        drift_types.append("ops_flow")
        alerts.append("稼働導線変化")

    if "island_id" in hist.columns and hist["island_id"].notna().any():
        h_top = hist.groupby("island_id")["diff_coins"].mean().sort_values(ascending=False)
        r_top = rec.groupby("island_id")["diff_coins"].mean().sort_values(ascending=False)
        h_set = set(h_top.head(3).index.astype(str))
        r_set = set(r_top.head(3).index.astype(str))
        if len(h_set & r_set) < 2 and len(h_set) >= 2:
            drift_score += 0.25
            drift_types.append("island_composition")
            alerts.append("島構成変更 — 強島入替")

        if len(h_top) >= 2 and len(r_top) >= 2 and h_top.index[0] != r_top.index[0]:
            drift_score += 0.18
            drift_types.append("release_position")
            alerts.append("放出位置変更")

    if "machine_number" in hist.columns:
        h_corner = hist[hist["machine_number"].astype(int) % 10 <= 1]["diff_coins"].mean()
        r_corner = rec[rec["machine_number"].astype(int) % 10 <= 1]["diff_coins"].mean()
        if pd.notna(h_corner) and pd.notna(r_corner) and float(r_corner) < float(h_corner) - 300:
            drift_score += 0.15
            drift_types.append("corner_favor_lost")
            alerts.append("角優遇消失の疑い")

    if prior_audit:
        for key, label in (
            ("specific_day_dependency_ratio", "特定日依存"),
            ("diff_dependency_ratio", "差枚依存"),
            ("ops_dependency_ratio", "稼働依存"),
        ):
            if float(prior_audit.get(key, 0)) > 0.55:
                drift_score += 0.12
                alerts.append(f"{label} — 過学習リスク")

    drift_score = min(1.0, drift_score)
    historical_weight = max(0.15, 1.0 - drift_score * 0.75)
    recent_weight = min(2.0, 1.0 + drift_score * 0.85)
    ev_confidence_penalty = round(drift_score * 0.35, 3)

    if drift_score > 0.5 and not alerts:
        alerts.append("特徴量ドリフト検出")

    return {
        "drift_score": round(drift_score, 3),
        "alerts": alerts,
        "drift_types": drift_types,
        "signals": {
            "mean_diff_shift": round(mean_shift, 1),
            "ops_shift": round(r_ops - h_ops, 3),
        },
        "historical_weight": round(historical_weight, 3),
        "recent_weight": round(recent_weight, 3),
        "historical_weight_decay": round(historical_weight, 3),
        "prefer_recent": drift_score > 0.35,
        "stop_legacy_features": drift_score > 0.55,
        "ev_confidence_penalty": ev_confidence_penalty,
    }


def apply_drift_weight_decay(base_weight: float, drift: dict) -> float:
    return round(base_weight * float(drift.get("historical_weight_decay", 1.0)), 4)
