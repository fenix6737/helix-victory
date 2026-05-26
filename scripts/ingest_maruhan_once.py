"""マルハン梅田 — 保存済みJSONを ingest → backfill → 分析（管理者認証）"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

API = os.getenv("API_URL", "http://127.0.0.1:8000")
STORE = "maruhan_umeda"
DATA = ROOT / "collector" / "samples" / "e2e" / "maruhan_umeda_full.json"


async def main() -> int:
    if not DATA.is_file():
        print(f"Missing {DATA} — run collect_maruhan_live.py first")
        return 1

    logs = json.loads(DATA.read_text(encoding="utf-8"))
    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "")
    if not pw:
        print("ADMIN_PASSWORD not set in .env")
        return 1

    print(f"[ingest] {STORE} rows={len(logs)}")
    async with httpx.AsyncClient(timeout=300) as c:
        login = await c.post(f"{API}/api/v1/auth/login", json={"username": user, "password": pw})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

        ing = await c.post(
            f"{API}/api/v1/ingest/logs",
            json={"store_id": STORE, "logs": logs},
            headers=auth,
        )
        ing.raise_for_status()
        print(f"  {ing.json()}")

        bf = await c.post(f"{API}/api/v1/stores/{STORE}/backfill-game-types", headers=auth)
        print(f"  backfill {bf.json()}")

        ar = await c.post(
            f"{API}/api/v1/analysis/run",
            headers=auth,
            json={"store_id": STORE, "run_feedback": True},
        )
        ar.raise_for_status()
        body = ar.json()
        print(f"  analysis rec={body.get('recommendations_created')} danger={body.get('danger_level')}")

        for gt in ("slot", "pachinko", "all"):
            rec = await c.get(
                f"{API}/api/v1/recommendations/today",
                params={"store_id": STORE, "game_type": gt},
                headers=auth,
            )
            if rec.status_code == 200:
                d = rec.json()
                print(
                    f"  [{gt}] recommend={len(d['recommend'])} "
                    f"hold={len(d['hold'])} exclude={len(d['exclude_preview'])}"
                )
            else:
                print(f"  [{gt}] HTTP {rec.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
