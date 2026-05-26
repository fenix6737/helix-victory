"""プレイ記録 CRUD"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlayRecord
from app.schemas import PlayRecordIn, PlayRecordOut


def _to_out(row: PlayRecord) -> PlayRecordOut:
    return PlayRecordOut(
        id=row.id,
        store_id=row.store_id,
        machine_id=row.machine_id,
        machine_number=row.machine_number,
        title=row.title,
        game_type=row.game_type,
        invest_yen=row.invest_yen,
        result_yen=row.result_yen,
        note=row.note,
        played_at=row.played_at,
        net_yen=row.result_yen - row.invest_yen,
    )


async def list_play_records(db: AsyncSession, store_id: str, limit: int = 50) -> list[PlayRecordOut]:
    result = await db.execute(
        select(PlayRecord)
        .where(PlayRecord.store_id == store_id)
        .order_by(PlayRecord.played_at.desc())
        .limit(limit)
    )
    return [_to_out(r) for r in result.scalars().all()]


async def create_play_record(db: AsyncSession, body: PlayRecordIn) -> PlayRecordOut:
    row = PlayRecord(
        store_id=body.store_id,
        machine_id=body.machine_id,
        machine_number=body.machine_number,
        title=body.title,
        game_type=body.game_type,
        invest_yen=body.invest_yen,
        result_yen=body.result_yen,
        note=body.note[:256],
        played_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


async def delete_play_record(db: AsyncSession, record_id: int) -> bool:
    row = await db.get(PlayRecord, record_id)
    if not row:
        return False
    await db.delete(row)
    await db.commit()
    return True
