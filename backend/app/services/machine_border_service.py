"""m_machine_borders CRUD + CSVインポート"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.machine_borders import DEFAULT_BORDERS, BorderSpec, match_border
from app.models import MachineBorder


async def list_borders(db: AsyncSession) -> list[BorderSpec]:
    rows = (await db.execute(select(MachineBorder).order_by(MachineBorder.title_pattern))).scalars().all()
    if not rows:
        return [BorderSpec(**d) for d in DEFAULT_BORDERS]
    return [
        BorderSpec(
            title_pattern=r.title_pattern,
            border_per_1000_yen=r.border_per_1000_yen,
            game_type=r.game_type,
            coin_price_yen=r.coin_price_yen,
            base_games=r.base_games,
        )
        for r in rows
    ]


async def seed_default_borders(db: AsyncSession) -> int:
    existing = await db.execute(select(MachineBorder.id).limit(1))
    if existing.scalar_one_or_none():
        return 0
    for d in DEFAULT_BORDERS:
        db.add(MachineBorder(**d))
    await db.commit()
    return len(DEFAULT_BORDERS)


async def import_borders_csv(db: AsyncSession, csv_text: str, *, replace: bool = False) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    required = {"title_pattern", "border_per_1000_yen"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise ValueError("CSV must have columns: title_pattern, border_per_1000_yen [,game_type,coin_price_yen,base_games]")

    if replace:
        await db.execute(delete(MachineBorder))

    count = 0
    for row in reader:
        pat = (row.get("title_pattern") or "").strip()
        if not pat:
            continue
        border = float(row["border_per_1000_yen"])
        db.add(
            MachineBorder(
                title_pattern=pat,
                border_per_1000_yen=border,
                game_type=(row.get("game_type") or "pachinko").strip(),
                coin_price_yen=float(row.get("coin_price_yen") or 4.0),
                base_games=int(row.get("base_games") or 400),
            )
        )
        count += 1
    await db.commit()
    return {"imported": count, "replaced": replace}


async def lookup_border(db: AsyncSession, title: str) -> BorderSpec | None:
    rows = await list_borders(db)
    return match_border(title, rows)
