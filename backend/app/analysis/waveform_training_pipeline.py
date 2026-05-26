"""波形教師学習パイプライン — 長期ログ蓄積後に実行"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from app.analysis.waveform_ml import analyze_waveform_series, extract_waveform_features


def prepare_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Sequence特徴量 + ラベル（実結果）の学習用フレーム"""
    rows: list[dict] = []
    for machine_id, g in df.groupby("machine_id"):
        g = g.sort_values("captured_at")
        diffs = g["diff_coins"].tolist()
        wf = analyze_waveform_series(diffs)
        actual = float(g["diff_coins"].dropna().mean()) if g["diff_coins"].notna().any() else 0.0
        label = "setting_like" if wf["is_setting_like"] and actual > 0 else "accident" if wf["is_accident_wave"] else "neutral"
        row = {**wf["features"], "label": label, "actual_diff": actual, "machine_id": int(machine_id)}
        rows.append(row)
    return pd.DataFrame(rows)


def train_waveform_models(df: pd.DataFrame, min_samples: int = 200) -> dict:
    """
    LightGBM / XGBoost / CatBoost があればアンサンブル。なければルールのみ。
    """
    frame = prepare_training_frame(df)
    if len(frame) < min_samples:
        return {
            "status": "insufficient_data",
            "required": min_samples,
            "got": len(frame),
            "message": "最低3ヶ月分のログ蓄積後に再実行",
        }

    try:
        import lightgbm as lgb
    except ImportError:
        return {"status": "skipped", "reason": "lightgbm not installed", "samples": len(frame)}

    X = frame.drop(columns=["label", "actual_diff", "machine_id"], errors="ignore")
    y = (frame["actual_diff"] > 0).astype(int)

    model = lgb.LGBMClassifier(n_estimators=80, max_depth=5, verbose=-1)
    model.fit(X, y)
    imp = dict(zip(X.columns, model.feature_importances_.tolist()))

    out_path = Path(os.getenv("WAVEFORM_MODEL_PATH", "data/waveform_lgb.txt"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(out_path))

    return {
        "status": "trained",
        "samples": len(frame),
        "positive_rate": float(y.mean()),
        "feature_importance": imp,
        "model_path": str(out_path),
    }
