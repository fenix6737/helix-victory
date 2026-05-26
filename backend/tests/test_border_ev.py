"""ボーダー・回転率スコアの単体テスト"""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from app.analysis.border_ev import border_ev_score, estimate_rotation_per_250, tail_digit_strength


class TestBorderEv(unittest.TestCase):
    def test_tail_digit_weekday(self):
        self.assertGreater(tail_digit_strength(107, 2), tail_digit_strength(100, 0))

    def test_rotation_from_games(self):
        g = pd.DataFrame(
            {
                "rotation_count": [None, None],
                "final_games": [500, 600],
                "diff_coins": [100, 200],
                "big_count": [1, 2],
                "reg_count": [0, 1],
                "captured_at": pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC"),
            }
        )
        rot = estimate_rotation_per_250(g)
        self.assertIsNotNone(rot)
        self.assertGreater(rot, 0)

    def test_border_score_slot(self):
        g = pd.DataFrame(
            {
                "rotation_count": [7000, 7500],
                "final_games": [500, 520],
                "diff_coins": [-200, 300],
                "big_count": [2, 3],
                "reg_count": [1, 1],
                "captured_at": pd.date_range("2026-05-01", periods=2, freq="D", tz="UTC"),
            }
        )
        score, reasons = border_ev_score(
            g, 101, "スマスロ北斗", "slot", date(2026, 5, 20), {"event_days": [3]}
        )
        self.assertGreater(score, 0.2)
        self.assertTrue(reasons)


if __name__ == "__main__":
    unittest.main()
