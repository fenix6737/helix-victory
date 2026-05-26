"""波形ML v4 — 設定/事故/回収/放出/崩壊入口"""

from __future__ import annotations

import numpy as np

from app.analysis.engine import classify_waveform


def extract_waveform_features(diffs: np.ndarray) -> dict[str, float]:
    if len(diffs) < 3:
        return {
            "slope": 0.0,
            "spike_rate": 0.0,
            "drop_rate": 0.0,
            "v_shape_rate": 0.0,
            "flat_rate": 1.0,
            "reversal_count": 0.0,
            "continuity": 0.0,
            "island_sync_hint": 0.0,
            "late_rise": 0.0,
        }

    d = diffs.astype(float)
    n = len(d)
    x = np.arange(n, dtype=float)
    slope = float(np.polyfit(x, d, 1)[0]) if n >= 2 else 0.0

    deltas = np.diff(d)
    spike_rate = float(np.mean(deltas > 400)) if len(deltas) else 0.0
    drop_rate = float(np.mean(deltas < -400)) if len(deltas) else 0.0

    mid = n // 2
    v_shape = 0.0
    if n >= 4:
        left_min = float(np.min(d[:mid]))
        right = float(d[mid:].max())
        if left_min < d[0] - 200 and right > left_min + 500:
            v_shape = 1.0

    late_rise = 0.0
    if n >= 5:
        late = float(d[-2:].mean() - d[:2].mean())
        if late > 400:
            late_rise = 1.0

    span = float(d.max() - d.min()) if n else 0.0
    flat_rate = float(1.0 - min(span / 2000.0, 1.0))

    signs = np.sign(deltas)
    reversals = int(np.sum(signs[1:] * signs[:-1] < 0)) if len(signs) > 1 else 0

    continuity = 0.0
    if len(deltas) >= 2:
        same_dir = np.sum(deltas[1:] * deltas[:-1] > 0)
        continuity = float(same_dir / max(len(deltas) - 1, 1))

    return {
        "slope": round(slope, 2),
        "spike_rate": round(spike_rate, 3),
        "drop_rate": round(drop_rate, 3),
        "v_shape_rate": round(v_shape, 3),
        "flat_rate": round(flat_rate, 3),
        "reversal_count": float(reversals),
        "continuity": round(continuity, 3),
        "island_sync_hint": round(continuity * (1 - flat_rate), 3),
        "late_rise": late_rise,
    }


def classify_waveform_ml(features: dict[str, float], rule_fallback: str | None = None) -> str:
    slope = features.get("slope", 0)
    spike = features.get("spike_rate", 0)
    drop = features.get("drop_rate", 0)
    v = features.get("v_shape_rate", 0)
    flat = features.get("flat_rate", 0)
    cont = features.get("continuity", 0)
    late = features.get("late_rise", 0)
    island_sync_hint = features.get("island_sync_hint", 0)

    if spike > 0.3 and slope < 20 and cont < 0.35:
        return "fake_release"
    if drop > 0.35 and spike > 0.25:
        return "trap_wave"
    if v > 0.5 and slope < 0:
        return "early_peak"
    if late > 0 and slope > 30:
        return "late_release"
    if flat > 0.65 and slope > 15 and cont > 0.45:
        return "stable_growth"
    if flat > 0.72 and abs(slope) < 25:
        return "stable_setting"
    if flat > 0.8 and slope < -40:
        return "exhausted"
    if drop > 0.3 and cont < 0.25 and island_sync_hint < 0.2:
        return "collapse_entry"
    if drop > 0.4 and slope < -80:
        return "forced_recovery" if cont > 0.4 else "death_wave"
    if drop > 0.4:
        return "death_wave"
    if v > 0.5:
        return "v_shape"
    if spike > 0.35 and cont < 0.4:
        return "one_shot"
    if slope > 60 and cont > 0.5:
        return "right_shoulder"
    if slope > 40 and spike > 0.2:
        return "release"
    if flat > 0.7 and abs(slope) < 30:
        return "setting_like"
    if rule_fallback:
        return rule_fallback
    return "unknown"


def _ml_model_adjust(feats: dict[str, float], rule_class: str) -> str | None:
    """学習済み LightGBM があれば補正（長期ログ後）"""
    import os
    from pathlib import Path

    path = Path(os.getenv("WAVEFORM_MODEL_PATH", "data/waveform_lgb.txt"))
    if not path.is_file():
        return None
    try:
        import lightgbm as lgb

        booster = lgb.Booster(model_file=str(path))
        cols = booster.feature_name()
        row = [feats.get(c, 0.0) for c in cols]
        prob = float(booster.predict([row])[0])
        if prob > 0.62:
            return "stable_growth" if feats.get("slope", 0) > 20 else "setting_like"
        if prob < 0.28:
            return "trap_wave"
    except Exception:
        return None
    return None


def analyze_waveform_series(diffs: list[float | int | None], rule_waveform: str | None = None) -> dict:
    arr = np.array([x for x in diffs if x is not None], dtype=float)
    feats = extract_waveform_features(arr)
    ml_class = classify_waveform_ml(feats, rule_fallback=rule_waveform)
    adj = _ml_model_adjust(feats, ml_class)
    if adj and ml_class in ("unknown", rule_waveform):
        ml_class = adj
    setting_like = ml_class in (
        "stable_setting",
        "setting_like",
        "right_shoulder",
        "release",
        "late_release",
    )
    accident = ml_class in (
        "death_wave",
        "death",
        "one_shot",
        "trap_wave",
        "fake_release",
        "early_peak",
    )
    recovery = ml_class in ("forced_recovery", "death_wave", "death")
    trap_penalty = ml_class in ("fake_release", "trap_wave", "death_wave", "early_peak")
    return {
        "features": feats,
        "ml_class": ml_class,
        "is_setting_like": setting_like,
        "is_accident_wave": accident,
        "is_recovery_wave": recovery,
        "trap_penalty": trap_penalty,
        "fake_release": ml_class == "fake_release",
        "trap_wave": ml_class == "trap_wave",
    }
