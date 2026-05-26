"""開発者指示書 §3 — 1日/週/月統計の構造検証"""
from __future__ import annotations

import asyncio
import os
import unittest
from datetime import date

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///c:/Helix Victory/backend/helix_local.db",
)


class DeveloperSpecPeriodStats(unittest.IsolatedAsyncioTestCase):
    async def test_daily_weekly_monthly_shapes(self):
        from app.db import async_session
        from app.services import period_statistics

        store_id = "kicona_amagasaki"
        async with async_session() as db:
            daily = await period_statistics.get_daily_statistics(db, store_id)
            weekly = await period_statistics.get_weekly_statistics(db, store_id)
            monthly = await period_statistics.get_monthly_statistics(
                db, store_id, date.today().year, date.today().month
            )

        for key in ("machine_count", "big_hit_total", "recommendation_count", "prediction"):
            self.assertIn(key, daily, f"daily missing {key}")
        self.assertEqual(daily["period"], "daily")

        for key in ("hit_rate_trend", "machine_ranking", "prediction"):
            self.assertIn(key, weekly, f"weekly missing {key}")
        self.assertEqual(len(weekly["hit_rate_trend"]), 7)
        self.assertEqual(weekly["period"], "weekly")

        for key in ("prediction_accuracy", "machine_family_trends"):
            self.assertIn(key, monthly, f"monthly missing {key}")
        self.assertEqual(monthly["period"], "monthly")


if __name__ == "__main__":
    unittest.main()
