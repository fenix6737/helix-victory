"""マルハン梅田 — 推奨・保留が返ること（回帰）"""
from __future__ import annotations

import asyncio
import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///c:/Helix Victory/backend/helix_local.db",
)


class MaruhanRecommendationsTest(unittest.IsolatedAsyncioTestCase):
    async def test_maruhan_has_recommend_and_hold(self):
        from app.db import async_session
        from app.services import recommendations

        async with async_session() as db:
            out = await recommendations.get_today_recommendations(
                db, "maruhan_umeda", game_type="pachinko"
            )
        self.assertIsNotNone(out)
        assert out is not None
        self.assertGreater(len(out.recommend), 0)
        self.assertGreater(len(out.hold), 0)


if __name__ == "__main__":
    unittest.main()
