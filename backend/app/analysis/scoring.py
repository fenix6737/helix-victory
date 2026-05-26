"""推奨スコア生成 — LightGBM / XGBoost / CatBoost + ルールベース"""

import os
from datetime import date

import numpy as np
import pandas as pd

from app.config import settings

REASON_TEMPLATES = {
    "sunk_days": "・{n}日間凹み",
    "corner2": "・角2配置",
    "corner": "・角配置",
    "hold": "・据え置き傾向",
    "weekday": "・特定日一致",
    "island": "・島全体強化傾向",
    "past_inject": "・過去同条件投入率高",
    "recover": "・回収後投入パターン",
    "wave_morning": "・朝から右肩波形",
    "wave_one_shot": "・一撃型波形",
    "wave_evening": "・夕方急伸",
    "wave_ops": "・稼働急変",
}


def _rule_score(row: pd.Series) -> float:
    score = 50.0
    score += min(row.get("sunk_days", 0) * 8, 24)
    score += row.get("is_corner2", 0) * 12
    score += row.get("is_corner", 0) * 6
    score += row.get("hold_score", 0) * 8
    score += row.get("specific_day_score", 0) * 5
    score += row.get("island_boost", 0) * 10
    score += row.get("recover_inject", 0) * 8
    score += row.get("wave_morning_rise", 0) * 5
    score += row.get("wave_one_shot", 0) * 6
    score += row.get("wave_evening_spike", 0) * 5
    score -= row.get("missing_rate", 0) * 40
    return float(np.clip(score, 0, 100))


def _build_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    n = int(row.get("sunk_days", 0))
    if n >= 2:
        reasons.append(REASON_TEMPLATES["sunk_days"].format(n=n))
    if row.get("is_corner2"):
        reasons.append(REASON_TEMPLATES["corner2"])
    elif row.get("is_corner"):
        reasons.append(REASON_TEMPLATES["corner"])
    if row.get("hold_score"):
        reasons.append(REASON_TEMPLATES["hold"])
    if row.get("specific_day_score"):
        reasons.append(REASON_TEMPLATES["weekday"])
    if row.get("island_boost"):
        reasons.append(REASON_TEMPLATES["island"])
    if row.get("recover_inject"):
        reasons.append(REASON_TEMPLATES["recover"])
    if row.get("wave_morning_rise"):
        reasons.append(REASON_TEMPLATES["wave_morning"])
    if row.get("wave_one_shot"):
        reasons.append(REASON_TEMPLATES["wave_one_shot"])
    if row.get("wave_evening_spike"):
        reasons.append(REASON_TEMPLATES["wave_evening"])
    if row.get("wave_ops_sudden") or row.get("wave_abnormal_ops"):
        reasons.append(REASON_TEMPLATES["wave_ops"])
    if not reasons:
        reasons.append("・店舗傾向・時系列から相対評価")
    return reasons


def _ensemble_ml(features: pd.DataFrame) -> np.ndarray | None:
    try:
        import lightgbm as lgb
        import xgboost as xgb
        from catboost import CatBoostRegressor
    except ImportError:
        return None

    model_dir = os.path.join(os.path.dirname(__file__), "..", "..", "models")
    lgb_path = os.path.join(model_dir, "lgb_rank.txt")
    xgb_path = os.path.join(model_dir, "xgb_rank.json")
    cat_path = os.path.join(model_dir, "cat_rank.cbm")

    if not all(os.path.exists(p) for p in (lgb_path, xgb_path, cat_path)):
        return None

    feature_cols = [c for c in features.columns if c != "machine_id"]
    X = features[feature_cols].fillna(0)

    lgb_model = lgb.Booster(model_file=lgb_path)
    xgb_model = xgb.Booster()
    xgb_model.load_model(xgb_path)
    cat_model = CatBoostRegressor()
    cat_model.load_model(cat_path)

    s1 = lgb_model.predict(X)
    s2 = xgb_model.predict(xgb.DMatrix(X))
    s3 = cat_model.predict(X)
    blended = 0.4 * s1 + 0.35 * s2 + 0.25 * s3
    return np.clip(blended, 0, 100)


def score_machines(features: pd.DataFrame, target_date: date) -> list[dict]:
    if features.empty:
        return []

    ml_scores = _ensemble_ml(features)
    results = []

    for i, row in features.iterrows():
        missing_rate = float(row.get("missing_rate", 0))
        sample_count = int(row.get("sample_count", 0))

        if missing_rate > settings.analysis_missing_rate_max:
            continue
        confidence = 0.3 if sample_count < settings.analysis_min_samples else min(
            0.95, 0.5 + sample_count / 500
        )

        if ml_scores is not None:
            idx = list(features.index).index(i)
            score = float(ml_scores[idx])
        else:
            score = _rule_score(row)

        results.append(
            {
                "machine_id": int(row["machine_id"]),
                "score": round(score, 1),
                "reasons": _build_reasons(row),
                "sample_count": sample_count,
                "period_days": 90,
                "confidence": round(confidence, 2),
                "has_missing_data": missing_rate > 0.1,
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank

    return results[:20]
