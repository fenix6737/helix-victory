import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Machine, RawLog, Recommendation, StoreMetadata
from app.schemas import StoreLiveStatusOut


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def get_store_live_status(db: AsyncSession, store_id: str) -> StoreLiveStatusOut:
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    last_ingest = await db.scalar(
        select(func.max(RawLog.captured_at)).where(RawLog.store_id == store_id)
    )
    last_analysis = await db.scalar(
        select(func.max(Recommendation.created_at)).where(Recommendation.store_id == store_id)
    )
    meta_row = await db.get(StoreMetadata, store_id)
    last_sync = meta_row.updated_at if meta_row else None

    log_count = await db.scalar(
        select(func.count(RawLog.id)).where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= since_24h,
        )
    ) or 0

    machines = await db.execute(select(Machine.game_type).where(Machine.store_id == store_id))
    types = [r[0] or "slot" for r in machines.all()]
    slot_count = sum(1 for t in types if t == "slot")
    pachinko_count = sum(1 for t in types if t == "pachinko")

    poll = int(os.getenv("FRONTEND_POLL_INTERVAL_SEC", "30"))
    stale_minutes = int(os.getenv("LIVE_STALE_MINUTES", "20"))
    analysis_stale_minutes = int(os.getenv("ANALYSIS_STALE_MINUTES", "25"))
    now = datetime.now(timezone.utc)
    is_stale = True
    ingest_age_min: int | None = None
    sync_age_min: int | None = None
    analysis_age_min: int | None = None

    if last_ingest:
        ingest_age_min = int((now - _utc(last_ingest)).total_seconds() // 60)

    if last_sync:
        sync_age_min = int((now - _utc(last_sync)).total_seconds() // 60)
        is_stale = (now - _utc(last_sync)) > timedelta(minutes=stale_minutes)
    elif last_ingest:
        is_stale = (now - _utc(last_ingest)) > timedelta(minutes=stale_minutes)

    is_analysis_stale = True
    if last_analysis:
        analysis_age_min = int((now - _utc(last_analysis)).total_seconds() // 60)
        is_analysis_stale = (now - _utc(last_analysis)) > timedelta(minutes=analysis_stale_minutes)

    collect_peak = os.getenv("COLLECTOR_INTERVAL_PEAK_SEC", "45")
    collect_normal = os.getenv("COLLECTOR_INTERVAL_NORMAL_SEC", "180")

    return StoreLiveStatusOut(
        store_id=store_id,
        last_ingest_at=last_ingest,
        last_sync_at=last_sync,
        last_analysis_at=last_analysis,
        log_count_24h=log_count,
        machine_count=len(types),
        slot_count=slot_count,
        pachinko_count=pachinko_count,
        poll_interval_sec=poll,
        is_stale=is_stale,
        has_any_data=last_ingest is not None,
        ingest_age_minutes=ingest_age_min,
        sync_age_minutes=sync_age_min,
        analysis_age_minutes=analysis_age_min,
        is_analysis_stale=is_analysis_stale,
        realtime_mode=(
            f"収集{collect_peak}〜{collect_normal}秒→取込→分析→UI{poll}秒更新"
        ),
    )
