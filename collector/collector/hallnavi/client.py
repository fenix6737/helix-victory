"""ホールナビ — 店舗情報取得"""

import logging
import os
from typing import Any

import httpx

from collector.hallnavi.parser import parse_hall_info

logger = logging.getLogger("hallnavi")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_URL = "https://hall-navi.com/hole_view?hid=660088400000027290"


async def fetch_hall_navi_info(
    store_id: str,
    url: str | None = None,
) -> dict[str, Any]:
    url = url or os.getenv("HALLNAVI_KICONA_URL", DEFAULT_URL)
    status: dict[str, Any] = {
        "source": "hall_navi",
        "url": url,
        "ok": False,
        "error": None,
        "info": {},
    }
    try:
        async with httpx.AsyncClient(
            timeout=45.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            res = await client.get(url)
            res.raise_for_status()
            info = parse_hall_info(res.text)
            status["info"] = info
            status["ok"] = bool(info.get("hall_name") or info.get("address"))
            if not status["ok"]:
                status["error"] = "no hall fields parsed"
            logger.info("[%s] hall-navi ok=%s", store_id, status["ok"])
            return status
    except Exception as e:
        status["error"] = str(e)
        logger.warning("[%s] hall-navi failed: %s", store_id, e)
        return status
