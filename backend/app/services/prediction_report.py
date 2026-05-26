"""毎日の大当たり予測レポート — 保存・照合（開発者指示書 2）"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.featured import classify_featured
from app.models import DailyPredictionReport, Recommendation


async def build_and_save_daily_report(
    db: AsyncSession,
    store_id: str,
    target_date: date,
    *,
    data_sources: dict | None = None,
) -> dict:
    stmt = (
        select(Recommendation)
        .where(
            Recommendation.store_id == store_id,
            Recommendation.target_date == target_date,
            Recommendation.tier == "recommend",
        )
        .options(joinedload(Recommendation.machine))
        .order_by(Recommendation.rank)
        .limit(30)
    )
    recs = list((await db.execute(stmt)).scalars().unique().all())
    predictions = []
    for r in recs:
        m = r.machine
        feat, gid, badge = classify_featured(m.title if m else "")
        predictions.append(
            {
                "rank": r.rank,
                "machine_id": r.machine_id,
                "machine_number": m.machine_number if m else 0,
                "title": m.title if m else "",
                "score": round(r.score, 2),
                "tier": r.tier,
                "is_featured": feat,
                "featured_group": gid,
                "featured_badge": badge,
                "reasons": json.loads(r.reasons) if r.reasons.startswith("[") else [r.reasons],
            }
        )

    missing_sources = []
    if data_sources:
        for name, st in data_sources.items():
            if isinstance(st, dict) and not st.get("ok"):
                missing_sources.append(
                    {"source": name, "error": st.get("error", "unavailable")}
                )

    report_json = {
        "target_date": target_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prediction_count": len(predictions),
        "predictions": predictions,
        "featured_count": sum(1 for p in predictions if p["is_featured"]),
        "missing_sources": missing_sources,
    }

    existing = await db.execute(
        select(DailyPredictionReport).where(
            DailyPredictionReport.store_id == store_id,
            DailyPredictionReport.target_date == target_date,
        )
    )
    row = existing.scalar_one_or_none()
    if row:
        row.report_json = json.dumps(report_json, ensure_ascii=False)
        row.data_sources_json = json.dumps(data_sources or {}, ensure_ascii=False)
        row.generated_at = datetime.now(timezone.utc)
    else:
        db.add(
            DailyPredictionReport(
                store_id=store_id,
                target_date=target_date,
                report_json=json.dumps(report_json, ensure_ascii=False),
                data_sources_json=json.dumps(data_sources or {}, ensure_ascii=False),
            )
        )
    await db.commit()
    return report_json


async def get_latest_report(
    db: AsyncSession, store_id: str, target_date: date | None = None
) -> dict | None:
    stmt = select(DailyPredictionReport).where(
        DailyPredictionReport.store_id == store_id
    )
    if target_date:
        stmt = stmt.where(DailyPredictionReport.target_date == target_date)
    else:
        stmt = stmt.order_by(DailyPredictionReport.target_date.desc())
    row = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if not row:
        return None
    out = json.loads(row.report_json)
    out["hit_summary"] = (
        json.loads(row.hit_summary_json) if row.hit_summary_json else None
    )
    out["data_sources"] = (
        json.loads(row.data_sources_json) if row.data_sources_json else {}
    )
    return out


async def update_report_hit_summary(
    db: AsyncSession, store_id: str, eval_date: date
) -> None:
    """前日予測の照合結果をレポートに反映"""
    pred_date = eval_date - timedelta(days=1)
    row = (
        await db.execute(
            select(DailyPredictionReport).where(
                DailyPredictionReport.store_id == store_id,
                DailyPredictionReport.target_date == pred_date,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return
    from app.services.period_statistics import _prediction_stats

    summary = await _prediction_stats(db, store_id, eval_date, eval_date)
    row.hit_summary_json = json.dumps(summary, ensure_ascii=False)
    await db.commit()
