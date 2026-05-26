"""PS Cube 出玉情報 — httpx 取得"""

import logging
import os
from typing import Any

import httpx

from collector.pscube.parser import parse_pscube_machines

logger = logging.getLogger("pscube")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_URL = (
    "https://www.pscube.jp/dedamajyoho-P-townDMMpachi/c713842/"
)


async def scrape_pscube_store(
    store_id: str,
    url: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (rows, status) where status documents ok/missing for reports.
    """
    url = url or os.getenv("PSCUBE_KICONA_URL", DEFAULT_URL)
    status: dict[str, Any] = {
        "source": "pscube",
        "url": url,
        "ok": False,
        "row_count": 0,
        "error": None,
    }
    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            res = await client.get(url)
            res.raise_for_status()
            rows = parse_pscube_machines(res.text, store_id)
            status["ok"] = len(rows) > 0
            status["row_count"] = len(rows)
            if not rows:
                status["error"] = "parse yielded 0 machines"
            logger.info("[%s] pscube: %d rows", store_id, len(rows))
            return rows, status
    except Exception as e:
        status["error"] = str(e)
        logger.warning("[%s] pscube failed: %s", store_id, e)
        return [], status
