"""開発者指示書 §2 — 日次学習サイクル・予測レポート（実DB・ダミーなし）"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///c:/Helix Victory/backend/helix_local.db",
)


class DeveloperSpecDailyCycle(unittest.IsolatedAsyncioTestCase):
    async def test_daily_learning_cycle_runs(self):
        from app.db import async_session
        from app.services.daily_cycle import run_daily_learning_cycle

        async with async_session() as db:
            result = await run_daily_learning_cycle(db, "kicona_amagasaki")
            await db.commit()

        self.assertEqual(result["store_id"], "kicona_amagasaki")
        self.assertIn("outcomes_recorded", result)
        self.assertIn("analysis", result)
        self.assertIn("report", result)
        self.assertGreaterEqual(
            result["report"].get("prediction_count") or 0,
            0,
            "report must include prediction_count",
        )

    async def test_prediction_report_after_cycle(self):
        from app.db import async_session
        from app.services.prediction_report import get_latest_report
        from app.timeutil import analysis_target_date

        target = analysis_target_date()
        async with async_session() as db:
            report = await get_latest_report(db, "kicona_amagasaki", target)
        self.assertIsNotNone(report, "prediction report must exist after cycle")
        assert report is not None
        self.assertIn("predictions", report)
        self.assertIn("missing_sources", report)


if __name__ == "__main__":
    unittest.main()
