"""全検証スイート一括実行"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = [
    "scripts/verify_all.py",
    "scripts/combat_e2e_suite.py",
    "scripts/integrity_suite.py",
    "scripts/stale_suite.py",
    "scripts/collapse_suite.py",
    "scripts/drift_suite.py",
]


def main() -> int:
    failed = []
    for rel in SUITES:
        path = ROOT / rel
        print(f"\n=== {rel} ===")
        r = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
        if r.returncode != 0:
            failed.append(rel)
    if failed:
        print("\nFAILED:", failed)
        return 1
    print("\n=== ALL SUITES PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
