"""
ローカル E2E: 収集 → ingest → 分析

使い方:
  python scripts/e2e_local.py --store kicona_amagasaki
  python scripts/e2e_local.py --store kicona_amagasaki --scrape-only
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def scrape(store_id: str) -> list[dict]:
    from collector.scraper import scrape_store
    from collector.config import config

    url = config.store_urls[store_id]
    return await scrape_store(store_id, url)


async def ingest(api_url: str, store_id: str, logs: list[dict]) -> dict:
    key = os.getenv("INGEST_API_KEY", "")
    headers = {"X-Ingest-Key": key} if key else {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            f"{api_url.rstrip('/')}/api/v1/ingest/logs",
            json={"store_id": store_id, "logs": logs},
            headers=headers,
        )
        res.raise_for_status()
        return res.json()


async def login(api_url: str) -> str:
    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            f"{api_url.rstrip('/')}/api/v1/auth/login",
            json={"username": user, "password": pw},
        )
        res.raise_for_status()
        return res.json()["access_token"]


async def analyze(api_url: str, store_id: str, token: str) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post(
            f"{api_url.rstrip('/')}/api/v1/analysis/run",
            json={"store_id": store_id, "run_feedback": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        res.raise_for_status()
        return res.json()


async def health(api_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"{api_url.rstrip('/')}/health")
            return res.status_code == 200
    except Exception:
        return False


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="kicona_amagasaki")
    parser.add_argument("--scrape-only", action="store_true")
    parser.add_argument("--from-cache", action="store_true", help="Use collector/samples/e2e/{store}_full.json")
    parser.add_argument("--api-url", default=os.getenv("API_URL", "http://localhost:8000"))
    args = parser.parse_args()

    out_dir = ROOT / "collector" / "samples" / "e2e"
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_file = out_dir / f"{args.store}_full.json"
    if args.from_cache and cache_file.exists():
        print(f"[1/3] load cache {cache_file.name} ...")
        logs = json.loads(cache_file.read_text(encoding="utf-8"))
    else:
        print(f"[1/3] scrape {args.store} ...")
        logs = await scrape(args.store)
    out_file = out_dir / f"{args.store}_latest.json"
    full_file = out_dir / f"{args.store}_full.json"
    full_file.write_text(json.dumps(logs, ensure_ascii=False), encoding="utf-8")
    out_file.write_text(json.dumps(logs[:5], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  rows={len(logs)} sample_saved={out_file.name}")

    if args.scrape_only:
        return

    if not await health(args.api_url):
        print(
            f"[2/3] SKIP ingest — API unreachable at {args.api_url}\n"
            "  Start: docker compose up -d && cd backend && uvicorn app.main:app --port 8000"
        )
        return

    print("[2/3] ingest ...")
    ing = await ingest(args.api_url, args.store, logs)
    print(f"  inserted={ing.get('inserted')} skipped={ing.get('skipped')}")

    print("[3/3] analysis ...")
    token = await login(args.api_url)
    result = await analyze(args.api_url, args.store, token)
    print(f"  recommendations={result.get('recommendations_created')}")
    print(f"  tiers={result.get('tier_counts')}")


if __name__ == "__main__":
    asyncio.run(main())
