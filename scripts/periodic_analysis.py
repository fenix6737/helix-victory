"""PC常時稼働用 — 収集データから分析＋実績照合（ユーザー未操作でも的中率を更新）"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

ROOT = __file__
for _ in range(3):
    ROOT = os.path.dirname(ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

API = os.getenv("API_URL", "http://127.0.0.1:8000")
USER = os.getenv("ADMIN_USERNAME", "helix_admin")
PASS = os.getenv("ADMIN_PASSWORD", "")
STORES = os.getenv("COLLECT_STORES", "kicona_amagasaki,maruhan_umeda").split(",")


async def main() -> int:
    if not PASS:
        print("ADMIN_PASSWORD not set")
        return 1
    async with httpx.AsyncClient(timeout=300) as c:
        login = await c.post(f"{API}/api/v1/auth/login", json={"username": USER, "password": PASS})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for sid in [s.strip() for s in STORES if s.strip()]:
            r = await c.post(
                f"{API}/api/v1/analysis/run",
                headers=auth,
                json={"store_id": sid, "run_feedback": True},
            )
            print(f"{sid}: analysis {r.status_code}")
            p = await c.get(
                f"{API}/api/v1/stores/{sid}/performance",
                headers=auth,
                params={"game_type": "all"},
            )
            if p.status_code == 200:
                rec = p.json()["recommend"]["days_7"]
                print(f"  recommend 7d plus: {rec.get('plus_rate_pct')}% ({rec.get('prediction_count')}件)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
