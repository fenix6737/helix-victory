"""推奨一覧 — infer_position 未定義の回帰防止（pytest 不要で実行可）"""
from __future__ import annotations

import asyncio
import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///c:/Helix Victory/backend/helix_local.db",
)


class RecommendationsTodayTest(unittest.IsolatedAsyncioTestCase):
    async def test_slot_recommendations_non_empty(self):
        from app.db import async_session
        from app.services import recommendations

        async with async_session() as db:
            out = await recommendations.get_today_recommendations(
                db, "kicona_amagasaki", game_type="slot"
            )
        self.assertIsNotNone(out)
        assert out is not None
        self.assertGreater(len(out.recommend), 0)
        self.assertEqual(out.recommend[0].rank, 1)


if __name__ == "__main__":
    unittest.main()
