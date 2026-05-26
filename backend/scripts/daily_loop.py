"""日次ループ: 検証 → 重み調整 → 翌日分析

Usage:
  python scripts/daily_loop.py maruhan_umeda
  python scripts/daily_loop.py kicona_amagasaki
"""

import asyncio
import os
import sys

import httpx

API = os.getenv("API_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "helix_admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")


async def main(store_id: str) -> None:
    async with httpx.AsyncClient(timeout=120.0) as client:
        login = await client.post(
            f"{API}/api/v1/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r = await client.post(
            f"{API}/api/v1/analysis/daily-loop",
            json={"store_id": store_id},
            headers=headers,
        )
        r.raise_for_status()
        print(r.json())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python daily_loop.py <store_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
