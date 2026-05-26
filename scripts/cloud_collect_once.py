"""クラウド常時稼働用 — 全店舗を1回収集→ingest→分析（GitHub Actions から実行）"""
from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> int:
    auth_b64 = os.getenv("DAIDATA_AUTH_B64", "").strip()
    auth_path = os.getenv("DAIDATA_STORAGE_STATE", "collector/daidata_auth.json")
    full_auth = ROOT / auth_path
    if auth_b64 and not full_auth.is_file():
        full_auth.parent.mkdir(parents=True, exist_ok=True)
        full_auth.write_bytes(base64.b64decode(auth_b64))

    from collector.config import config
    from collector.ingest_client import post_logs
    from collector.scraper import scrape_store
    import httpx

    api = os.getenv("HELIX_API_URL") or os.getenv("API_URL", "")
    if not api:
        print("Set HELIX_API_URL (cloud API base, e.g. https://helix-victory.fly.dev)")
        return 1

    stores = os.getenv("COLLECT_STORES", "kicona_amagasaki,maruhan_umeda").split(",")
    stores = [s.strip() for s in stores if s.strip()]

    for sid in stores:
        url = config.store_urls.get(sid)
        if not url:
            print(f"skip unknown store: {sid}")
            continue
        print(f"[collect] {sid} ...")
        try:
            logs = await scrape_store(sid, url)
        except Exception as e:
            print(f"  scrape failed: {e}")
            continue
        print(f"  rows={len(logs)}")
        if not logs:
            continue
        result = await post_logs(api, sid, logs)
        print(f"  ingest: {result}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print("  ingest 401 Unauthorized — INGEST_API_KEY mismatch. Run scripts/sync-github-secrets.ps1")
        raise

    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "")
    if not pw:
        print("ADMIN_PASSWORD not set — skip analysis")
        return 0

    async with httpx.AsyncClient(timeout=180) as c:
        login = await c.post(f"{api}/api/v1/auth/login", json={"username": user, "password": pw})
        if login.status_code != 200:
            print(f"analysis login failed: {login.status_code}")
            return 1
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        for sid in stores:
            ar = await c.post(
                f"{api}/api/v1/analysis/run",
                headers=auth,
                json={"store_id": sid, "run_feedback": True},
            )
            snippet = ar.text[:200].encode("utf-8", errors="replace").decode("utf-8")
            print(f"[analysis] {sid}: HTTP {ar.status_code} {snippet}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
