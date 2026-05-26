"""1日 / 週 / 月 統計（開発者指示書 3）"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.featured import classify_featured
from app.models import Machine, PredictionOutcome, RawLog, Recommendation
from app.timeutil import JST, analysis_target_date, jst_day_bounds_utc, jst_today


async def _latest_log_day_jst(db: AsyncSession, store_id: str) -> date | None:
    """取り込みログの最新日（JST）。captured_at はスクレイプ日付基準のため今日0件時に使用。"""
    row = await db.execute(
        select(func.max(RawLog.captured_at)).where(RawLog.store_id == store_id)
    )
    ts = row.scalar()
    if not ts:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(JST).date()


async def _machines_active_today(
    db: AsyncSession, store_id: str, day: date
) -> list[dict]:
    since, until = jst_day_bounds_utc(day)
    stmt = (
        select(
            Machine.machine_number,
            Machine.title,
            func.count(RawLog.id).label("samples"),
            func.sum(RawLog.diff_coins).label("diff_sum"),
            func.sum(RawLog.big_count).label("bb_sum"),
        )
        .join(Machine, Machine.id == RawLog.machine_id)
        .where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= since,
            RawLog.captured_at < until,
        )
        .group_by(Machine.id, Machine.machine_number, Machine.title)
        .order_by(func.sum(RawLog.diff_coins).desc())
    )
    rows = await db.execute(stmt)
    out = []
    for r in rows.all():
        feat, gid, badge = classify_featured(r.title or "")
        out.append(
            {
                "machine_number": r.machine_number,
                "title": r.title,
                "samples": int(r.samples or 0),
                "diff_sum": int(r.diff_sum or 0),
                "big_hits": int(r.bb_sum or 0),
                "is_featured": feat,
                "featured_group": gid,
                "featured_badge": badge,
            }
        )
    return out


async def _prediction_stats(
    db: AsyncSession, store_id: str, since: date, until: date
) -> dict:
    stmt = select(PredictionOutcome).where(
        PredictionOutcome.store_id == store_id,
        PredictionOutcome.eval_date >= since,
        PredictionOutcome.eval_date <= until,
        PredictionOutcome.actual_diff_mean.isnot(None),
    )
    outcomes = list((await db.execute(stmt)).scalars().all())
    if not outcomes:
        return {
            "evaluated": 0,
            "hits": 0,
            "hit_rate_pct": None,
            "recommend_hit_rate_pct": None,
        }
    hits = sum(1 for o in outcomes if o.hit)
    rec = [o for o in outcomes if o.predicted_tier == "recommend"]
    rec_hits = sum(1 for o in rec if o.hit)
    return {
        "evaluated": len(outcomes),
        "hits": hits,
        "hit_rate_pct": round(100.0 * hits / len(outcomes), 1),
        "recommend_hit_rate_pct": (
            round(100.0 * rec_hits / len(rec), 1) if rec else None
        ),
    }


async def get_daily_statistics(
    db: AsyncSession, store_id: str, target_date: date | None = None
) -> dict:
    day = target_date or jst_today()
    machines = await _machines_active_today(db, store_id, day)
    if not machines and not target_date:
        latest = await _latest_log_day_jst(db, store_id)
        if latest:
            day = latest
            machines = await _machines_active_today(db, store_id, day)

    pred = await _prediction_stats(db, store_id, jst_today(), jst_today())

    rec_target = target_date or analysis_target_date()
    rec_stmt = select(func.count(Recommendation.id)).where(
        Recommendation.store_id == store_id,
        Recommendation.target_date == rec_target,
        Recommendation.tier == "recommend",
    )
    rec_count = int((await db.execute(rec_stmt)).scalar() or 0)

    big_total = sum(m["big_hits"] for m in machines)
    return {
        "period": "daily",
        "date": day.isoformat(),
        "store_id": store_id,
        "machine_count": len(machines),
        "big_hit_total": big_total,
        "recommendation_count": rec_count,
        "prediction": pred,
        "top_machines": machines[:20],
        "featured_machines": [m for m in machines if m["is_featured"]][:15],
    }


async def get_weekly_statistics(
    db: AsyncSession, store_id: str, end_date: date | None = None
) -> dict:
    end = end_date or jst_today()
    start = end - timedelta(days=6)
    pred = await _prediction_stats(db, store_id, start, end)

    series = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_pred = await _prediction_stats(db, store_id, d, d)
        series.append(
            {
                "date": d.isoformat(),
                "hit_rate_pct": day_pred["hit_rate_pct"],
                "evaluated": day_pred["evaluated"],
            }
        )

    since_dt, _ = jst_day_bounds_utc(start)
    _, until_dt = jst_day_bounds_utc(end)
    rank_stmt = (
        select(
            Machine.machine_number,
            Machine.title,
            func.sum(RawLog.diff_coins).label("diff_sum"),
        )
        .join(Machine, Machine.id == RawLog.machine_id)
        .where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= since_dt,
            RawLog.captured_at < until_dt,
        )
        .group_by(Machine.id, Machine.machine_number, Machine.title)
        .order_by(func.sum(RawLog.diff_coins).desc())
        .limit(15)
    )
    rank_rows = await db.execute(rank_stmt)
    ranking = [
        {
            "machine_number": r.machine_number,
            "title": r.title,
            "diff_sum": int(r.diff_sum or 0),
            "is_featured": classify_featured(r.title or "")[0],
        }
        for r in rank_rows.all()
    ]

    return {
        "period": "weekly",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "store_id": store_id,
        "prediction": pred,
        "hit_rate_trend": series,
        "machine_ranking": ranking,
    }


async def get_monthly_statistics(
    db: AsyncSession, store_id: str, year: int | None = None, month: int | None = None
) -> dict:
    now = jst_today()
    y = year or now.year
    m = month or now.month
    start = date(y, m, 1)
    if m == 12:
        end = date(y, 12, 31)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)

    pred = await _prediction_stats(db, store_id, start, end)

    since_dt, _ = jst_day_bounds_utc(start)
    _, until_dt = jst_day_bounds_utc(end)
    fam_stmt = (
        select(Machine.title, func.count(RawLog.id), func.avg(RawLog.diff_coins))
        .join(Machine, Machine.id == RawLog.machine_id)
        .where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= since_dt,
            RawLog.captured_at < until_dt,
        )
        .group_by(Machine.title)
    )
    rows = await db.execute(fam_stmt)
    by_title: dict[str, dict] = {}
    for title, cnt, avg_diff in rows.all():
        feat, gid, _ = classify_featured(title or "")
        key = gid or "other"
        if key not in by_title:
            by_title[key] = {
                "group": key,
                "titles": [],
                "samples": 0,
                "avg_diff": 0.0,
            }
        by_title[key]["titles"].append(title)
        by_title[key]["samples"] += int(cnt or 0)
        if avg_diff is not None:
            by_title[key]["avg_diff"] += float(avg_diff)

    return {
        "period": "monthly",
        "year": y,
        "month": m,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "store_id": store_id,
        "prediction_accuracy": pred,
        "machine_family_trends": list(by_title.values()),
    }
