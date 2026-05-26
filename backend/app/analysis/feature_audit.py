"""Feature Importance 監査 — 差枚単独依存の過学習を検知"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from app.analysis.engine import LayerWeights, classify_waveform


def _waveform_distribution(df: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, g in df.groupby("machine_id"):
        wf = classify_waveform(g.sort_values("captured_at"))
        key = wf.value
        counts[key] = counts.get(key, 0) + 1
    return counts


def run_feature_audit(
    df: pd.DataFrame,
    scored: list[dict],
    weights: LayerWeights,
    target_date: date,
) -> dict:
    """
    推奨層の根拠が差枚・特定日・稼働のどれに偏っているかを監査。
    日次で保存し、重み変化の追跡に使う。
    """
    alerts: list[str] = []
    recs = [s for s in scored if s.get("tier") == "recommend"]

    diff_heavy = 0
    day_heavy = 0
    ops_heavy = 0
    wave_heavy = 0
    corner_heavy = 0

    for s in recs:
        reasons = " ".join(s.get("reasons") or [])
        if "凹み" in reasons or "差枚" in reasons or "低期待" in reasons:
            diff_heavy += 1
        if "特定日" in reasons or "曜" in reasons:
            day_heavy += 1
        if "稼働" in reasons:
            ops_heavy += 1
        if "波形" in reasons or "右肩" in reasons or "一撃" in reasons:
            wave_heavy += 1
        if "角" in reasons:
            corner_heavy += 1

    n = max(len(recs), 1)
    diff_ratio = diff_heavy / n
    day_ratio = day_heavy / n
    ops_ratio = ops_heavy / n
    wave_ratio = wave_heavy / n
    corner_ratio = corner_heavy / n

    if diff_ratio > 0.65:
        alerts.append("差枚・凹み理由が推奨の65%超 — 差枚依存過多")
    if day_ratio > 0.55:
        alerts.append("特定日理由が過多 — カレンダー過学習の疑い")
    if ops_ratio > 0.5:
        alerts.append("稼働理由が過多 — 稼働ノイズ依存の疑い")
    if wave_ratio < 0.1 and len(recs) >= 10:
        alerts.append("波形根拠が少ない — 設定挙動の見落とし")
    if corner_ratio > 0.6:
        alerts.append("角配置理由が過多 — 角依存の疑い")

    recent = df[pd.to_datetime(df["captured_at"]).dt.date >= target_date - pd.Timedelta(days=7)]
    diff_only_signal = 0.0
    if not recent.empty and recent["diff_coins"].notna().sum() > 50:
        daily = recent.groupby(recent["captured_at"].dt.date)["diff_coins"].mean()
        if len(daily) >= 3:
            vol = float(daily.std())
            if vol < 80:
                diff_only_signal = 0.8
                alerts.append("直近7日の店舗差枚が横ばい — 差枚だけでは判別困難")

    return {
        "recommend_count": len(recs),
        "diff_dependency_ratio": round(diff_ratio, 3),
        "specific_day_dependency_ratio": round(day_ratio, 3),
        "ops_dependency_ratio": round(ops_ratio, 3),
        "waveform_reason_ratio": round(wave_ratio, 3),
        "corner_dependency_ratio": round(corner_ratio, 3),
        "diff_flat_signal": round(diff_only_signal, 3),
        "weights": weights.to_dict(),
        "waveform_distribution": _waveform_distribution(df),
        "alerts": alerts,
        "eval_metrics_hint": {
            "primary": "expected_value_improvement",
            "secondary": ["exclude_precision", "recovery_avoidance", "store_pattern_match"],
            "forbidden_primary": "hit_rate_only",
        },
    }
