"""
LightGBM / XGBoost / CatBoost 学習。

Usage:
  python train_models.py exported.csv 2026-05-24
"""

import os
import sys
from datetime import date

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.analysis.features import build_features  # noqa: E402

FEATURE_COLS = [
    "sunk_days",
    "diff_range_7d",
    "hold_score",
    "rot_mean",
    "missing_rate",
    "is_corner",
    "is_corner2",
    "weekday_match",
    "specific_day_score",
    "island_boost",
    "recover_inject",
    "latest_diff",
    "wave_morning_rise",
    "wave_one_shot",
    "wave_evening_spike",
    "wave_abnormal_ops",
    "wave_ops_sudden",
]

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "models")


def train_from_csv(csv_path: str, target_date_str: str) -> None:
    import lightgbm as lgb
    import xgboost as xgb
    from catboost import CatBoostRegressor, Pool

    df = pd.read_csv(csv_path, parse_dates=["captured_at"])
    if "weekday" not in df.columns:
        df["weekday"] = pd.to_datetime(df["captured_at"]).dt.weekday

    target_date = date.fromisoformat(target_date_str)
    features = build_features(df, target_date)

    if "label" not in df.columns:
        print("CSVに label 列が必要です（export_training_data.py で生成）")
        sys.exit(1)

    labels = (
        df.groupby("machine_id")["label"]
        .last()
        .reindex(features["machine_id"])
        .fillna(0.5)
        .values
    )

    X = features[FEATURE_COLS].fillna(0)
    y = labels

    os.makedirs(MODEL_DIR, exist_ok=True)

    lgb_train = lgb.Dataset(X, label=y)
    lgb_model = lgb.train(
        {"objective": "regression", "metric": "rmse", "verbosity": -1},
        lgb_train,
        num_boost_round=200,
    )
    lgb_model.save_model(os.path.join(MODEL_DIR, "lgb_rank.txt"))

    dtrain = xgb.DMatrix(X, label=y)
    xgb_model = xgb.train(
        {"objective": "reg:squarederror", "verbosity": 0},
        dtrain,
        num_boost_round=200,
    )
    xgb_model.save_model(os.path.join(MODEL_DIR, "xgb_rank.json"))

    cat_model = CatBoostRegressor(iterations=200, verbose=0)
    cat_model.fit(Pool(X, y))
    cat_model.save_model(os.path.join(MODEL_DIR, "cat_rank.cbm"))

    print(f"Models saved to {MODEL_DIR} ({len(FEATURE_COLS)} features)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python train_models.py <csv> <target_date YYYY-MM-DD>")
        sys.exit(1)
    train_from_csv(sys.argv[1], sys.argv[2])
