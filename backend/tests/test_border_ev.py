"""ボーダー・回転率スコアの単体テスト"""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from app.analysis.border_ev import border_ev_score
from app.analysis.machine_borders import (
    BorderSpec,
    border_exceed_score,
    estimate_rotation_per_1000_yen,
    match_border,
)


class TestBorderEv(unittest.TestCase):
    def test_match_evangelion(self):
        specs = [BorderSpec("エヴァンゲリオン", 16.5, "pachinko", 4.0, 400)]
        m = match_border("Pエヴァンゲリオン未来への咆哮", specs)
        self.assertIsNotNone(m)
        self.assertAlmostEqual(m.border_per_1000_yen, 16.5)

    def test_border_exceed(self):
        score, exceeded = border_exceed_score(18.0, 16.5, margin=1.0)
        self.assertTrue(exceeded)
        self.assertGreater(score, 0.5)

    def test_rotation_estimate(self):
        spec = BorderSpec("テスト", 17.0, "pachinko", 4.0, 400)
        rot, inv = estimate_rotation_per_1000_yen(5000, 400, spec, -500)
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
                "machine_number": [101, 101],
                "captured_at": pd.date_range("2026-05-01", periods=2, freq="D", tz="UTC"),
            }
        )
        specs = [BorderSpec("ジャグラー", 22.0, "slot", 20.0, 250)]
        score, reasons, rot_k, exceeded = border_ev_score(
            g, 101, "マイジャグラーV", "slot", date(2026, 5, 20), {}, specs, store_df=g
        )
        self.assertGreater(score, 0.1)
        self.assertTrue(reasons)


if __name__ == "__main__":
    unittest.main()
