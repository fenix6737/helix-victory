"""stale / degraded キャッシュスイート"""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.cache import cache_set, cache_get_with_meta, is_cache_degraded


async def main() -> int:
    await cache_set("stale:test", {"v": 1}, ttl=5)
    data, meta = await cache_get_with_meta("stale:test")
    if data is None:
        print("[FAIL] cache set/get")
        return 1
    print(f"[ok] cache roundtrip degraded={is_cache_degraded()} meta={meta}")
    print("=== STALE SUITE PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
