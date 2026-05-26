"""自動リカバリ提案 — collector/API/ingest/分析"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from app.cache import cache_get, get_redis


async def check_system_health(api_url: str | None = None) -> dict:
    api_url = api_url or os.getenv("API_URL", "http://127.0.0.1:8000")
    actions: list[str] = []
    status: dict[str, str] = {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{api_url.rstrip('/')}/health")
            status["api"] = "ok" if r.status_code == 200 else "down"
    except Exception:
        status["api"] = "down"
        actions.append("uvicorn を再起動: cd backend && py -3.12 -m uvicorn app.main:app --port 8000")

    try:
        r = await get_redis()
        await r.ping()
        status["redis"] = "ok"
    except Exception:
        status["redis"] = "down"
        actions.append("Redis起動: docker compose up -d redis")

    from app.cache import is_cache_degraded

    status["cache"] = "degraded" if is_cache_degraded() else "ok"
    if status["cache"] == "degraded":
        actions.append("degraded mode: メモリキャッシュ使用中 — stale警告あり")

    return {
        "status": status,
        "healthy": status.get("api") == "ok",
        "degraded": status.get("redis") != "ok" or status.get("cache") == "degraded",
        "recovery_actions": actions,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def recovery_playbook(issue: str) -> list[str]:
    books = {
        "ingest_failed": [
            "INGEST_API_KEY を確認",
            "py -3.12 scripts/e2e_local.py --store kicona_amagasaki --from-cache",
        ],
        "analysis_failed": [
            "POST /api/v1/analysis/run を再実行",
            "integrity_guardian の issues を確認",
        ],
        "collector_stopped": [
            "py -3.12 -m collector.daemon --stores kicona_amagasaki",
        ],
        "cache_corrupt": [
            "Redis FLUSHDB または cache_delete_pattern 実行",
        ],
    }
    return books.get(issue, ["logs を確認し ops_priority1.ps1 を実行"])
