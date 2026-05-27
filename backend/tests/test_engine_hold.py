"""期待値モードで保留枠が維持されること"""

from __future__ import annotations

import unittest
from datetime import date, timedelta

import pandas as pd

from app.analysis.engine import analyze_store


def _synthetic_df() -> pd.DataFrame:
    rows = []
    base = pd.Timestamp("2026-05-20", tz="UTC")
    for i in range(60):
        mn = 100 + i
        rot = 5500 + (i % 12) * 200
        for d in range(35):
            rows.append(
                {
                "machine_id": i + 1,
                "machine_number": mn,
                "captured_at": base + timedelta(days=d),
                "diff_coins": -400 + (i % 8) * 150,
                "rotation_count": rot,
                "big_count": 1 + (i % 3),
                "reg_count": 0,
                "final_games": 420 + (i % 5) * 10,
                "graph_samples_json": None,
                "is_operating": True,
                "position_type": "normal",
                "island_id": f"block_{mn // 100}",
                "title": f"Pエヴァンゲリオン未来への咆哮 {mn}",
                "game_type": "pachinko",
            }
            )
    return pd.DataFrame(rows)


class TestEngineHold(unittest.TestCase):
    def test_ev_mode_keeps_hold_tier(self):
        out = analyze_store(
            _synthetic_df(),
            "kicona_amagasaki",
            date(2026, 5, 27),
            ev_mode=True,
        )
        holds = [r for r in out if r["tier"] == "hold"]
        recs = [r for r in out if r["tier"] == "recommend"]
        self.assertGreaterEqual(len(holds), 3, f"holds={len(holds)} recs={len(recs)}")


if __name__ == "__main__":
    unittest.main()
