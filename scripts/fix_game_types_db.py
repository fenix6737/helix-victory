"""DB上の game_type をタイトルから再分類（API再起動不要）"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from sqlalchemy import select

from app.db import async_session
from app.game_type import classify_game_type
from app.models import Machine


async def main() -> None:
    store_id = os.getenv("STORE_ID", "kicona_amagasaki")
    async with async_session() as db:
        result = await db.execute(select(Machine).where(Machine.store_id == store_id))
        updated = 0
        slot_n = pach_n = 0
        for m in result.scalars().all():
            gt = classify_game_type(m.title)
            if gt == "slot":
                slot_n += 1
            else:
                pach_n += 1
            if m.game_type != gt:
                m.game_type = gt
                updated += 1
        await db.commit()
        print(f"store={store_id} updated={updated} slot={slot_n} pachinko={pach_n}")


if __name__ == "__main__":
    asyncio.run(main())
