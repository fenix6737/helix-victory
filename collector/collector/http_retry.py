"""HTTP リトライ — GitHub Actions / クラウド収集の一時障害対策"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

T = TypeVar("T")

RETRY_STATUS = {408, 429, 500, 502, 503, 504}


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 4,
    base_delay: float = 2.0,
    retry_on: Callable[[Exception], bool] | None = None,
) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last = e
            if retry_on and not retry_on(e):
                raise
            if i >= attempts - 1:
                raise
            delay = base_delay * (2**i)
            print(f"  retry {i + 1}/{attempts - 1} in {delay:.0f}s: {e}")
            await asyncio.sleep(delay)
    raise last  # pragma: no cover


def is_retryable_http(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUS
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    return False
