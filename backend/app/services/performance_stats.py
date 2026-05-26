"""実績ダッシュボード — 推奨・保留のプラス率（7日/30日）"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Machine, PredictionOutcome, RawLog, Recommendation
from app.services import live_status
from app.timeutil import jst_today


def _plus_rate(outcomes: list[PredictionOutcome]) -> dict:
    if not outcomes:
        return {
            "sample_days": 0,
            "prediction_count": 0,
            "plus_count": 0,
            "plus_rate_pct": None,
            "hit_rate_pct": None,
            "avg_diff": None,
        }
    plus = sum(1 for o in outcomes if (o.actual_diff_mean or 0) > 0)
    hits = sum(1 for o in outcomes if o.hit)
    diffs = [o.actual_diff_mean for o in outcomes if o.actual_diff_mean is not None]
    avg = sum(diffs) / len(diffs) if diffs else None
    days = len({o.eval_date for o in outcomes})
    n = len(outcomes)
    return {
        "sample_days": days,
        "prediction_count": n,
        "plus_count": plus,
        "plus_rate_pct": round(100.0 * plus / n, 1),
        "hit_rate_pct": round(100.0 * hits / n, 1),
        "avg_diff": round(avg, 0) if avg is not None else None,
    }


async def _tier_outcomes(
    db: AsyncSession,
    store_id: str,
    since: date,
    tier: str,
    game_type: str | None,
) -> list[PredictionOutcome]:
    stmt = (
        select(PredictionOutcome)
        .join(Machine, Machine.id == PredictionOutcome.machine_id)
        .where(
            PredictionOutcome.store_id == store_id,
            PredictionOutcome.eval_date >= since,
            PredictionOutcome.predicted_tier == tier,
            PredictionOutcome.actual_diff_mean.isnot(None),
        )
    )
    if game_type in ("slot", "pachinko"):
        stmt = stmt.where(Machine.game_type == game_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _daily_plus_series(
    db: AsyncSession,
    store_id: str,
    since: date,
    tier: str,
    game_type: str | None,
) -> list[dict]:
    stmt = (
        select(
            PredictionOutcome.eval_date,
            func.count(PredictionOutcome.id),
            func.sum(case((PredictionOutcome.actual_diff_mean > 0, 1), else_=0)),
        )
        .join(Machine, Machine.id == PredictionOutcome.machine_id)
        .where(
            PredictionOutcome.store_id == store_id,
            PredictionOutcome.eval_date >= since,
            PredictionOutcome.predicted_tier == tier,
            PredictionOutcome.actual_diff_mean.isnot(None),
        )
        .group_by(PredictionOutcome.eval_date)
        .order_by(PredictionOutcome.eval_date)
    )
    if game_type in ("slot", "pachinko"):
        stmt = stmt.where(Machine.game_type == game_type)
    rows = await db.execute(stmt)
    series = []
    for eval_d, total, plus in rows.all():
        if total and total > 0:
            series.append(
                {
                    "date": eval_d.isoformat(),
                    "plus_rate_pct": round(100.0 * (plus or 0) / total, 1),
                    "count": int(total),
                }
            )
    return series


async def get_performance_dashboard(
    db: AsyncSession,
    store_id: str,
    game_type: str = "all",
) -> dict:
    from app.analysis.feedback import adjust_weights, record_outcomes
    from app.services.analysis_settings import get_ev_mode

    today = jst_today()
    ev_mode = await get_ev_mode(db, store_id)
    recorded = await record_outcomes(db, store_id, today)
    await adjust_weights(db, store_id)
    since_7 = today - timedelta(days=7)
    since_30 = today - timedelta(days=30)
    gt = game_type if game_type in ("slot", "pachinko") else None

    rec_7 = await _tier_outcomes(db, store_id, since_7, "recommend", gt)
    rec_30 = await _tier_outcomes(db, store_id, since_30, "recommend", gt)
    hold_7 = await _tier_outcomes(db, store_id, since_7, "hold", gt)
    hold_30 = await _tier_outcomes(db, store_id, since_30, "hold", gt)

    live = await live_status.get_store_live_status(db, store_id)

    log_count = await db.execute(
        select(func.count(RawLog.id)).where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= datetime.now(timezone.utc) - timedelta(hours=24),
        )
    )
    logs_24h = int(log_count.scalar() or 0)

    outcome_total = await db.execute(
        select(func.count(PredictionOutcome.id)).where(
            PredictionOutcome.store_id == store_id,
        )
    )

    return {
        "store_id": store_id,
        "game_type": game_type,
        "generated_at": datetime.now(timezone.utc),
        "definition": "推奨・保留は「営業日の平均差枚がプラスか」で判定（JST営業日で予測と実績を照合）",
        "last_reconcile_count": recorded,
        "recommend": {
            "days_7": _plus_rate(rec_7),
            "days_30": _plus_rate(rec_30),
            "daily_7": await _daily_plus_series(db, store_id, since_7, "recommend", gt),
        },
        "hold": {
            "days_7": _plus_rate(hold_7),
            "days_30": _plus_rate(hold_30),
        },
        "operations": {
            "last_ingest_at": live.last_ingest_at.isoformat() if live.last_ingest_at else None,
            "last_analysis_at": (
                live.last_analysis_at.isoformat() if live.last_analysis_at else None
            ),
            "logs_24h": logs_24h,
            "is_stale": live.is_stale,
            "has_data": live.has_any_data,
            "outcomes_total": int(outcome_total.scalar() or 0),
        },
        "disclaimer": "勝利保証ではありません。データが溜まるほど％の信頼度が上がります。",
        "target_plus_rate_pct": 55.0,
        "ev_mode": ev_mode,
    }
