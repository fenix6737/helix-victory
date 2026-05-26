"""drift v3 スイート"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.analysis.drift_detection import detect_feature_drift


def main() -> int:
    hist = pd.DataFrame(
        {
            "diff_coins": [500] * 20,
            "is_operating": [True] * 20,
            "island_id": ["I1"] * 10 + ["I2"] * 10,
            "machine_number": list(range(20)),
            "captured_at": pd.date_range("2026-01-01", periods=20, freq="D", tz="UTC"),
        }
    )
    recent = pd.DataFrame(
        {
            "diff_coins": [-200] * 20,
            "is_operating": [False] * 20,
            "island_id": ["I3"] * 20,
            "machine_number": list(range(20)),
            "captured_at": pd.date_range("2026-05-01", periods=20, freq="D", tz="UTC"),
        }
    )
    d = detect_feature_drift(hist, recent)
    if d.get("historical_weight", 1) >= d.get("recent_weight", 1):
        print("[FAIL] weight decay not applied")
        return 1
    print(f"[ok] drift_score={d.get('drift_score')} hw={d.get('historical_weight')} rw={d.get('recent_weight')}")
    print("=== DRIFT SUITE PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
