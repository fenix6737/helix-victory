import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game_type import classify_game_type
from app.models import Machine, RawLog, StoreMetadata
from app.store_layout import get_machine_position
from app.schemas import RawLogIngestItem


async def upsert_machine(
    db: AsyncSession,
    store_id: str,
    machine_number: int,
    title: str,
    island_id: str | None,
    position_type: str | None,
    game_type: str | None = None,
) -> Machine:
    stmt = select(Machine).where(
        Machine.store_id == store_id,
        Machine.machine_number == machine_number,
    )
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()

    gtype = game_type or classify_game_type(title)
    if not position_type:
        position_type = get_machine_position(store_id, machine_number)

    if machine:
        machine.title = title
        machine.game_type = gtype
        if island_id:
            machine.island_id = island_id
        if position_type:
            machine.position_type = position_type
        return machine

    machine = Machine(
        store_id=store_id,
        machine_number=machine_number,
        title=title,
        game_type=gtype,
        island_id=island_id,
        position_type=position_type,
    )
    db.add(machine)
    await db.flush()
    return machine


async def ingest_logs(
    db: AsyncSession,
    store_id: str,
    items: list[RawLogIngestItem],
) -> tuple[int, int]:
    inserted = 0
    skipped = 0

    for item in items:
        if item.diff_coins is None and item.rotation_count is None:
            skipped += 1
            continue

        machine = await upsert_machine(
            db,
            store_id,
            item.machine_number,
            item.title,
            item.island_id,
            item.position_type,
            item.game_type,
        )

        log = RawLog(
            store_id=store_id,
            machine_id=machine.id,
            captured_at=item.captured_at,
            title=item.title,
            machine_number=item.machine_number,
            diff_coins=item.diff_coins,
            rotation_count=item.rotation_count,
            big_count=item.big_count,
            reg_count=item.reg_count,
            final_games=item.final_games,
            graph_url=item.graph_url,
            graph_samples_json=item.graph_samples_json,
            is_operating=item.is_operating,
            source=item.source or "collector",
        )
        db.add(log)
        inserted += 1

    if inserted:
        await _touch_store_sync(db, store_id)
    await db.commit()
    return inserted, skipped


async def _touch_store_sync(db: AsyncSession, store_id: str) -> None:
    now = datetime.now(timezone.utc)
    row = await db.get(StoreMetadata, store_id)
    if row:
        row.updated_at = now
    else:
        db.add(
            StoreMetadata(
                store_id=store_id,
                metadata_json=json.dumps({"updated_at": now.isoformat()}),
                updated_at=now,
            )
        )
