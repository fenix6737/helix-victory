"""オンライン学習 — 外した理由を記録し重みを更新"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.engine import LayerWeights
from app.analysis.feedback import adjust_weights, record_outcomes
from app.models import AnalysisWeights, PredictionOutcome, Recommendation


async def run_online_learning(
    db: AsyncSession,
    store_id: str,
    eval_date: date,
) -> dict:
    """
    1. 実結果記録
    2. 重み調整
    3. 失敗分析（外した理由）
    """
    n = await record_outcomes(db, store_id, eval_date)
    weights = await adjust_weights(db, store_id)

    since = eval_date.replace(day=1) if eval_date.day > 14 else eval_date
    from datetime import timedelta

    lookback = eval_date - timedelta(days=14)
    result = await db.execute(
        select(PredictionOutcome).where(
            PredictionOutcome.store_id == store_id,
            PredictionOutcome.eval_date >= lookback,
        )
    )
    outcomes = list(result.scalars().all())

    misses: list[dict] = []
    hits = 0
    for o in outcomes:
        if o.hit:
            hits += 1
        else:
            reason = "推奨外れ（実差枚マイナス）" if o.predicted_tier == "recommend" and (o.actual_diff_mean or 0) < 0 else "判定不一致"
            misses.append(
                {
                    "machine_id": o.machine_id,
                    "predicted_tier": o.predicted_tier,
                    "predicted_score": o.predicted_score,
                    "actual_diff_mean": o.actual_diff_mean,
                    "miss_reason": reason,
                    "eval_date": o.eval_date.isoformat(),
                }
            )

    hit_rate = hits / len(outcomes) if outcomes else 0.0
    exclude_ok = sum(
        1 for o in outcomes if o.predicted_tier == "exclude" and (o.actual_diff_mean or 0) < 0
    )
    exclude_total = sum(1 for o in outcomes if o.predicted_tier == "exclude") or 1

    summary = {
        "outcomes_recorded": n,
        "sample_size": len(outcomes),
        "recommend_hit_rate": round(hit_rate, 3),
        "exclude_precision": round(exclude_ok / exclude_total, 3),
        "miss_count": len(misses),
        "top_miss_reasons": _top_miss_reasons(misses),
        "weights": weights.to_dict(),
        "learned_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.commit()
    return summary


def _top_miss_reasons(misses: list[dict]) -> list[str]:
    from collections import Counter

    c = Counter(m["miss_reason"] for m in misses)
    return [f"{k}({v})" for k, v in c.most_common(3)]


async def get_learning_summary(db: AsyncSession, store_id: str) -> dict:
    from app.analysis.combat_history import list_snapshots

    snaps = list_snapshots(store_id, limit=5)
    for s in snaps:
        ol = s.get("payload", {}).get("online_learning")
        if ol:
            return ol
    row = await db.get(AnalysisWeights, store_id)
    if row and row.hit_rate_14d is not None:
        return {"recommend_hit_rate": row.hit_rate_14d, "source": "weights_table"}
    return {}
