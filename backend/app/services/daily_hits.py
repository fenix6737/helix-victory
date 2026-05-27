"""当日の当たり回数 — BB/RB（最新スナップショット基準）"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RawLog
from app.timeutil import jst_day_bounds_utc


def atari_total(big_count: int | None, reg_count: int | None) -> int | None:
    """スロット等: BB+RB。どちらか欠損はある方のみ、両方欠損は None。"""
    if big_count is None and reg_count is None:
        return None
    return int(big_count or 0) + int(reg_count or 0)


async def latest_logs_for_store_day(
    db: AsyncSession,
    store_id: str,
    day: date,
) -> dict[int, RawLog]:
    """店舗×日付ごと、台ごとに captured_at が最新の RawLog を返す。"""
    since, until = jst_day_bounds_utc(day)
    latest_sub = (
        select(
            RawLog.machine_id,
            func.max(RawLog.captured_at).label("max_at"),
        )
        .where(
            RawLog.store_id == store_id,
            RawLog.captured_at >= since,
            RawLog.captured_at < until,
        )
        .group_by(RawLog.machine_id)
    ).subquery()

    stmt = select(RawLog).join(
        latest_sub,
        and_(
            RawLog.machine_id == latest_sub.c.machine_id,
            RawLog.captured_at == latest_sub.c.max_at,
        ),
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {r.machine_id: r for r in rows}


def log_atari_fields(log: RawLog | None) -> tuple[int | None, int | None, int | None]:
    if not log:
        return None, None, None
    bb = log.big_count
    rb = log.reg_count
    return bb, rb, atari_total(bb, rb)
