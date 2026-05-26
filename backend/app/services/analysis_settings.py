"""店舗別分析モード（期待値 / オカルト）"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import StoreAnalysisSettings


async def get_ev_mode(db: AsyncSession, store_id: str) -> bool:
    """
    True = 期待値重視（オカルト排除）。
    未設定時は OCULT_MODE 環境変数の逆。
    """
    row = await db.get(StoreAnalysisSettings, store_id)
    if row is not None:
        return bool(row.ev_mode)
    return not settings.ocult_mode


async def set_ev_mode(db: AsyncSession, store_id: str, ev_mode: bool) -> None:
    row = await db.get(StoreAnalysisSettings, store_id)
    if row:
        row.ev_mode = ev_mode
    else:
        db.add(StoreAnalysisSettings(store_id=store_id, ev_mode=ev_mode))
    await db.commit()


async def get_settings_payload(db: AsyncSession, store_id: str) -> dict:
    ev = await get_ev_mode(db, store_id)
    return {
        "store_id": store_id,
        "ev_mode": ev,
        "ev_mode_label": "期待値重視（オカルト排除）" if ev else "オカルト・配置重視",
    }
