import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Machine, RawLog, Recommendation
from app.schemas import StoreLiveStatusOut


async def get_store_live_status(db: AsyncSession, store_id: str) -> StoreLiveStatusOut:
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    last_ingest = await db.scalar(
        select(func.max(RawLog.captured_at)).where(RawLog.store_id == store_id)
    )
    last_analysis = await db.scalar(
        select(func.max(Recommendation.created_at)).where(Recommendation.store_id == store_id)
    )
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
    is_stale = True
    if last_ingest:
        age = datetime.now(timezone.utc) - last_ingest.replace(tzinfo=timezone.utc)
        is_stale = age > timedelta(minutes=stale_minutes)

    return StoreLiveStatusOut(
        store_id=store_id,
        last_ingest_at=last_ingest,
        last_analysis_at=last_analysis,
        log_count_24h=log_count,
        machine_count=len(types),
        slot_count=slot_count,
        pachinko_count=pachinko_count,
        poll_interval_sec=poll,
        is_stale=is_stale,
        has_any_data=last_ingest is not None,
    )
