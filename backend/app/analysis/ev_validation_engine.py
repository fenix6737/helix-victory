"""EV検証 — 本当に期待値改善したか"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PredictionOutcome, Recommendation


async def validate_ev_performance(
    db: AsyncSession,
    store_id: str,
    target_date: date,
) -> dict:
    since = target_date - timedelta(days=14)

    out_result = await db.execute(
        select(PredictionOutcome).where(
            PredictionOutcome.store_id == store_id,
            PredictionOutcome.eval_date >= since,
        )
    )
    outcomes = list(out_result.scalars().all())

    rec_result = await db.execute(
        select(Recommendation).where(
            Recommendation.store_id == store_id,
            Recommendation.target_date >= since,
            Recommendation.tier == "recommend",
        )
    )
    recs = list(rec_result.scalars().all())

    if not outcomes:
        return {
            "before_ev": 0.0,
            "after_ev": 0.0,
            "improvement_rate": 0.0,
            "metrics": {},
            "sample_size": 0,
        }

    actuals = [o.actual_diff_mean for o in outcomes if o.actual_diff_mean is not None]
    before_ev = float(pd.Series(actuals).mean()) if actuals else 0.0

    recommend_outcomes = [o for o in outcomes if o.predicted_tier == "recommend"]
    rec_actuals = [o.actual_diff_mean for o in recommend_outcomes if o.actual_diff_mean is not None]
    after_ev = float(pd.Series(rec_actuals).mean()) if rec_actuals else before_ev

    improvement = 0.0
    if abs(before_ev) > 1:
        improvement = (after_ev - before_ev) / abs(before_ev)

    hit_rate = sum(1 for o in recommend_outcomes if o.hit) / max(len(recommend_outcomes), 1)
    exclude_outcomes = [o for o in outcomes if o.predicted_tier == "exclude"]
    exclude_ok = sum(1 for o in exclude_outcomes if (o.actual_diff_mean or 0) < 0)
    exclude_prec = exclude_ok / max(len(exclude_outcomes), 1)

    return {
        "before_ev": round(before_ev, 1),
        "after_ev": round(after_ev, 1),
        "improvement_rate": round(improvement, 3),
        "metrics": {
            "recommend_hit_rate": round(hit_rate, 3),
            "exclude_precision": round(exclude_prec, 3),
            "recommend_count": len(recs),
            "danger_avoidance_hint": round(exclude_prec, 3),
        },
        "sample_size": len(outcomes),
        "eval_primary": "expected_value_improvement",
    }
