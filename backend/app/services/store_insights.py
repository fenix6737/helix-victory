import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.analysis.danger_ml import score_danger_ml
from app.analysis.drift_detection import detect_feature_drift
from app.analysis.engine import LayerWeights
from app.analysis.feature_audit import run_feature_audit
from app.cache import cache_delete_pattern, cache_get, cache_set
from app.config import settings
from app.models import StoreDailyInsight, StoreMetadata
from app.schemas import StoreDailyInsightOut
from app.timeutil import analysis_target_date

import pandas as pd


async def build_and_save_insights(
    db: AsyncSession,
    store_id: str,
    df: pd.DataFrame,
    scored: list[dict],
    weights: LayerWeights,
    target: date,
) -> StoreDailyInsightOut:
    meta_row = await db.get(StoreMetadata, store_id)
    meta = json.loads(meta_row.metadata_json) if meta_row else {}
    event_days = meta.get("event_days") or [3, 9]

    danger = score_danger_ml(df, target, event_days)
    audit = run_feature_audit(df, scored, weights, target)
    drift = detect_feature_drift(
        df[pd.to_datetime(df["captured_at"]).dt.date < target - pd.Timedelta(days=7)],
        df[pd.to_datetime(df["captured_at"]).dt.date >= target - pd.Timedelta(days=7)],
        audit,
    )
    audit["drift"] = drift

    row = await db.get(StoreDailyInsight, (store_id, target))
    payload_audit = json.dumps(audit, ensure_ascii=False)
    payload_danger = json.dumps(danger.to_dict(), ensure_ascii=False)

    if row:
        row.danger_level = danger.level.value
        row.danger_score = danger.score
        row.should_play = danger.should_play
        row.headline = danger.headline
        row.danger_reasons_json = payload_danger
        row.feature_audit_json = payload_audit
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(
            StoreDailyInsight(
                store_id=store_id,
                target_date=target,
                danger_level=danger.level.value,
                danger_score=danger.score,
                should_play=danger.should_play,
                headline=danger.headline,
                danger_reasons_json=payload_danger,
                feature_audit_json=payload_audit,
            )
        )

    await db.flush()
    out = _to_out(store_id, target, danger, audit)
    await cache_set(f"insight:{store_id}:{target.isoformat()}", out.model_dump(), settings.cache_ttl_ranking)
    return out


async def get_daily_insight(
    db: AsyncSession,
    store_id: str,
    target_date: date | None = None,
) -> StoreDailyInsightOut | None:
    target = target_date or analysis_target_date()
    cache_key = f"insight:{store_id}:{target.isoformat()}"
    cached = await cache_get(cache_key)
    if cached:
        return StoreDailyInsightOut(**cached)

    row = await db.get(StoreDailyInsight, (store_id, target))
    if not row:
        return None

    danger = json.loads(row.danger_reasons_json)
    audit = json.loads(row.feature_audit_json)
    out = StoreDailyInsightOut(
        store_id=store_id,
        target_date=target,
        danger_level=row.danger_level,
        danger_score=row.danger_score,
        should_play=row.should_play,
        headline=row.headline,
        danger_reasons=danger.get("reasons", []),
        feature_audit=audit,
        store_mode=danger.get("store_mode"),
    )
    await cache_set(cache_key, out.model_dump(), settings.cache_ttl_ranking)
    return out


def _to_out(store_id: str, target: date, danger, audit: dict) -> StoreDailyInsightOut:
    d = danger.to_dict()
    return StoreDailyInsightOut(
        store_id=store_id,
        target_date=target,
        danger_level=d["level"],
        danger_score=d["score"],
        should_play=d["should_play"],
        headline=d["headline"],
        danger_reasons=d["reasons"],
        feature_audit=audit,
        store_mode=d.get("store_mode"),
    )
