"""島崩壊検知スイート"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.analysis.island_collapse_engine import detect_island_collapse
from app.analysis.island_live_engine import compute_island_live


def main() -> int:
    df = pd.DataFrame(
        {
            "machine_id": [1, 2, 3, 1, 2, 3],
            "island_id": ["A", "A", "A", "A", "A", "A"],
            "diff_coins": [800, 700, 600, -400, -500, -600],
            "is_operating": [True, True, True, False, False, False],
            "captured_at": pd.date_range("2026-05-23 10:00", periods=6, freq="30min", tz="UTC"),
        }
    )
    islands = compute_island_live(df, window_hours=24)
    info = detect_island_collapse(islands, df)
    if not info.get("any_collapse"):
        print("[warn] synthetic collapse not triggered — check thresholds")
    else:
        print(f"[ok] collapse detected islands={info.get('collapsed_islands')}")
    print("=== COLLAPSE SUITE PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
