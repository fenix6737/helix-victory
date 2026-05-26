import json
from typing import Any

import redis.asyncio as redis

from app.config import settings

_redis: redis.Redis | None = None
_memory_fallback: dict[str, tuple[Any, float]] = {}
_redis_degraded = False


async def get_redis() -> redis.Redis:
    global _redis, _redis_degraded
    if _redis_degraded:
        raise ConnectionError("redis unavailable")
    if _redis is None:
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.5,
        )
    try:
        await _redis.ping()
        return _redis
    except Exception:
        _redis_degraded = True
        _redis = None
        raise


def is_cache_degraded() -> bool:
    return _redis_degraded


CACHE_TTL = {
    "live_ev": 20,
    "live-ev": 20,
    "combat": 45,
    "retreat": 20,
    "island_state": 30,
    "island": 30,
    "danger": 60,
    "quantile": 30,
    "ranking": 90,
}


def ttl_for_key(key: str, default: int = 60) -> int:
    for prefix, ttl in CACHE_TTL.items():
        if key.startswith(prefix) or prefix in key:
            return ttl
    return default


async def cache_get(key: str) -> Any | None:
    data, _meta = await cache_get_with_meta(key)
    return data


async def cache_get_with_meta(key: str) -> tuple[Any | None, dict]:
    global _redis_degraded
    import time

    meta = {"stale": False, "degraded": False, "source": "redis"}
    try:
        r = await get_redis()
        raw = await r.get(key)
        if raw is not None:
            return json.loads(raw), meta
    except Exception:
        _redis_degraded = True
        meta["degraded"] = True
        meta["source"] = "memory"

    entry = _memory_fallback.get(key)
    if entry:
        value, expires = entry
        if time.time() < expires:
            meta["stale"] = _redis_degraded
            return value, meta
        del _memory_fallback[key]
    return None, meta


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    import time

    global _redis_degraded
    if ttl is None:
        ttl = ttl_for_key(key)
    if key.startswith("ranking:"):
        ttl = max(ttl, settings.cache_ttl_ranking)
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value, default=str))
        _memory_fallback[key] = (value, time.time() + ttl)
        return
    except Exception:
        _redis_degraded = True
    _memory_fallback[key] = (value, time.time() + ttl)


async def cache_delete_pattern(pattern: str) -> None:
    try:
        r = await get_redis()
        async for key in r.scan_iter(match=pattern):
            await r.delete(key)
    except Exception:
        pass
