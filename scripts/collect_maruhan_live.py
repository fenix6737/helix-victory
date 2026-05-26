"""マルハン梅田 — 本番収集（daidata 認証必須）→ ingest → 分析"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API = os.getenv("API_URL", "http://127.0.0.1:8000")
STORE = "maruhan_umeda"


async def main() -> int:
    auth_path = os.getenv("DAIDATA_STORAGE_STATE", "collector/daidata_auth.json")
    full = ROOT / auth_path
    if not full.is_file():
        print("daidata 未ログインです:")
        print("  py -3.12 collector/scripts/daidata_login.py")
        print("  ブラウザでログイン後 Enter → daidata_auth.json 作成")
        return 1

    from collector.scraper import scrape_store
    from collector.config import config
    import httpx

    url = config.store_urls.get(STORE, os.getenv("MARUHAN_UMEDA_URL"))
    print(f"[1/3] scrape {STORE} ...")
    logs = await scrape_store(STORE, url)
    print(f"  rows={len(logs)}")

    out = ROOT / "collector" / "samples" / "e2e" / "maruhan_umeda_full.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json

    out.write_text(json.dumps(logs, ensure_ascii=False), encoding="utf-8")

    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "")
    if not pw:
        print("ADMIN_PASSWORD not set in .env")
        return 1

    print("[2/3] ingest ...")
    async with httpx.AsyncClient(timeout=180) as c:
        login = await c.post(f"{API}/api/v1/auth/login", json={"username": user, "password": pw})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
        key = os.getenv("INGEST_API_KEY", "")
        ingest_headers = {**auth, **({"X-Ingest-Key": key} if key else {})}
        ing = await c.post(
            f"{API}/api/v1/ingest/logs",
            json={"store_id": STORE, "logs": logs},
            headers=ingest_headers,
        )
        ing.raise_for_status()
        print(f"  {ing.json()}")

        await c.post(f"{API}/api/v1/stores/{STORE}/backfill-game-types", headers=auth)
        print("[3/3] analysis ...")
        ar = await c.post(
            f"{API}/api/v1/analysis/run",
            headers=auth,
            json={"store_id": STORE, "run_feedback": True},
        )
        ar.raise_for_status()
        print(f"  {ar.json().get('recommendations_created')} rec danger={ar.json().get('danger_level')}")
        lev = await c.get(f"{API}/api/v1/stores/{STORE}/live-ev", headers=auth, params={"game_type": "all"})
        print(f"  live-ev HTTP {lev.status_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
