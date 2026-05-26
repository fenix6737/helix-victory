"""予測→実結果→重み再調整（日次ループ）"""

import json
from datetime import date, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.engine import LayerWeights
from app.models import AnalysisWeights, PredictionOutcome, RawLog, Recommendation


async def record_outcomes(
    db: AsyncSession,
    store_id: str,
    eval_date: date,
) -> int:
    """前日予測と当日実績を比較して保存"""
    pred_date = eval_date - timedelta(days=1)
    recs = await db.execute(
        select(Recommendation).where(
            Recommendation.store_id == store_id,
            Recommendation.target_date == pred_date,
        )
    )
    rec_list = list(recs.scalars().all())
    if not rec_list:
        return 0

    since = pd.Timestamp(eval_date, tz="UTC")
    until = pd.Timestamp(eval_date + timedelta(days=1), tz="UTC")

    count = 0
    for rec in rec_list:
        logs = await db.execute(
            select(RawLog.diff_coins)
            .where(
                RawLog.machine_id == rec.machine_id,
                RawLog.captured_at >= since,
                RawLog.captured_at < until,
            )
        )
        diffs = [r[0] for r in logs.all() if r[0] is not None]
        if not diffs:
            continue
        actual = float(np.mean(diffs))
        predicted_high = rec.tier == "recommend"
        actual_high = actual > 0
        hit = predicted_high == actual_high

        db.add(
            PredictionOutcome(
                store_id=store_id,
                machine_id=rec.machine_id,
                pred_date=pred_date,
                eval_date=eval_date,
                predicted_score=rec.score,
                predicted_tier=rec.tier,
                actual_diff_mean=actual,
                hit=hit,
            )
        )
        count += 1

    await db.commit()
    return count


async def adjust_weights(db: AsyncSession, store_id: str) -> LayerWeights:
    """直近14日の的中率からレイヤー重みを微調整"""
    since = date.today() - timedelta(days=14)
    result = await db.execute(
        select(PredictionOutcome).where(
            PredictionOutcome.store_id == store_id,
            PredictionOutcome.eval_date >= since,
        )
    )
    outcomes = list(result.scalars().all())

    row = await db.get(AnalysisWeights, store_id)
    base = LayerWeights.from_dict(json.loads(row.weights_json)) if row else LayerWeights()

    if len(outcomes) < 10:
        return base

    hit_rate = sum(1 for o in outcomes if o.hit) / len(outcomes)
    delta = (hit_rate - 0.5) * 0.15

    base.island = float(np.clip(base.island + delta, 0.7, 1.4))
    base.waveform = float(np.clip(base.waveform + delta, 0.7, 1.4))
    base.specific_day = float(np.clip(base.specific_day + delta * 0.8, 0.7, 1.4))
    base.exclusion_penalty = float(np.clip(base.exclusion_penalty + (0.5 - hit_rate) * 0.1, 0.8, 1.3))

    if row:
        row.weights_json = json.dumps(base.to_dict(), ensure_ascii=False)
        row.hit_rate_14d = hit_rate
        from datetime import datetime as dt

        row.updated_at = dt.now(timezone.utc)
    else:
        db.add(
            AnalysisWeights(
                store_id=store_id,
                weights_json=json.dumps(base.to_dict(), ensure_ascii=False),
                hit_rate_14d=hit_rate,
            )
        )
    await db.commit()
    return base
