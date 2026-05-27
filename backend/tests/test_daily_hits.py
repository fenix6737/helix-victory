"""当日当たり回数"""

from __future__ import annotations

import unittest

from app.services.daily_hits import atari_total


class TestDailyHits(unittest.TestCase):
    def test_atari_total_bb_rb(self):
        self.assertEqual(atari_total(20, 13), 33)
        self.assertEqual(atari_total(20, None), 20)
        self.assertIsNone(atari_total(None, None))

    def test_atari_zero(self):
        self.assertEqual(atari_total(0, 0), 0)


if __name__ == "__main__":
    unittest.main()
