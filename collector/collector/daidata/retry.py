"""指数バックオフ付きリトライ"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger("daidata.retry")

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
    label: str = "daidata",
) -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last = e
            if i < attempts - 1:
                delay = base_delay * (2**i)
                logger.warning("[%s] retry %d/%d in %.1fs: %s", label, i + 1, attempts, delay, e)
                await asyncio.sleep(delay)
    raise last  # type: ignore[misc]
