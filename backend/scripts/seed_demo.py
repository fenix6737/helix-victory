"""【開発専用】合成データ投入 — 本番運用では collector + 実サイトを使用すること"""

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone

import httpx

API = "http://localhost:8000"
STORE = "maruhan_umeda"

MACHINES = [
    (521, "L北斗", "corner2", "island_a"),
    (522, "L北斗", "corner", "island_a"),
    (301, "からくりサーカス", "row", "island_b"),
    (302, "からくりサーカス", "tail", "island_b"),
    (101, "東京リベンジャーズ", "corner2", "island_c"),
]


async def main():
    now = datetime.now(timezone.utc)
    logs = []

    for num, title, pos, island in MACHINES:
        base_diff = random.randint(-3000, 2000)
        for day_offset in range(7):
            for hour in [10, 14, 18, 22]:
                captured = now - timedelta(days=day_offset, hours=24 - hour)
                logs.append(
                    {
                        "machine_number": num,
                        "title": title,
                        "captured_at": captured.isoformat(),
                        "diff_coins": base_diff + random.randint(-500, 500) - day_offset * 200,
                        "rotation_count": random.randint(2000, 8000),
                        "big_count": random.randint(0, 15),
                        "reg_count": random.randint(0, 30),
                        "final_games": random.randint(0, 999),
                        "is_operating": random.random() > 0.2,
                        "island_id": island,
                        "position_type": pos,
                    }
                )

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{API}/api/v1/ingest/logs",
            json={"store_id": STORE, "logs": logs},
        )
        print("ingest:", r.json())
        r2 = await client.post(
            f"{API}/api/v1/analysis/run",
            json={"store_id": STORE},
        )
        print("analysis:", r2.json())
        r3 = await client.get(f"{API}/api/v1/recommendations/today?store_id={STORE}")
        data = r3.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
