"""信頼性極大化 — JST 営業日での予測照合"""

from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite+aiosqlite:///c:/Helix Victory/backend/helix_local.db",
)

from app.timeutil import JST, jst_day_bounds_utc, outcome_business_date


class TestOutcomeBusinessDate(unittest.TestCase):
    def test_previous_day(self):
        eval_d = date(2026, 5, 21)
        self.assertEqual(outcome_business_date(eval_d), date(2026, 5, 20))

    def test_jst_bounds(self):
        since, until = jst_day_bounds_utc(date(2026, 5, 20))
        cap = datetime(2026, 5, 20, 12, 0, tzinfo=JST).astimezone(timezone.utc)
        self.assertLessEqual(since, cap)
        self.assertLess(cap, until)


class TestRecordOutcomesIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_record_outcomes_on_local_db(self):
        from sqlalchemy import delete, select

        from app.analysis.feedback import record_outcomes
        from app.db import async_session
        from app.models import Machine, PredictionOutcome, RawLog, Recommendation

        store_id = "kicona_amagasaki"
        business = date(2099, 1, 15)
        eval_d = business + timedelta(days=1)
        since, until = jst_day_bounds_utc(business)
        cap = datetime(2099, 1, 15, 15, 0, tzinfo=JST).astimezone(timezone.utc)

        async with async_session() as db:
            await db.execute(
                delete(PredictionOutcome).where(
                    PredictionOutcome.store_id == store_id,
                    PredictionOutcome.pred_date == business,
                )
            )
            await db.execute(
                delete(Recommendation).where(
                    Recommendation.store_id == store_id,
                    Recommendation.target_date == business,
                )
            )
            m = Machine(
                store_id=store_id,
                machine_number=99901,
                title="照合テスト機",
                game_type="slot",
            )
            db.add(m)
            await db.flush()
            db.add(
                Recommendation(
                    store_id=store_id,
                    machine_id=m.id,
                    target_date=business,
                    rank=1,
                    tier="recommend",
                    score=88.0,
                    reasons="[]",
                )
            )
            db.add(
                RawLog(
                    store_id=store_id,
                    machine_id=m.id,
                    machine_number=99901,
                    title="照合テスト機",
                    captured_at=cap,
                    diff_coins=400,
                    source="test",
                )
            )
            await db.commit()

            n = await record_outcomes(db, store_id, eval_d)
            self.assertEqual(n, 1)
            self.assertLessEqual(since, cap)
            self.assertLess(cap, until)

            row = (
                await db.execute(
                    select(PredictionOutcome).where(
                        PredictionOutcome.store_id == store_id,
                        PredictionOutcome.pred_date == business,
                    )
                )
            ).scalar_one()
            self.assertTrue(row.hit)
            self.assertEqual(row.eval_date, eval_d)

            await db.execute(delete(Machine).where(Machine.id == m.id))
            await db.commit()


if __name__ == "__main__":
    unittest.main()
