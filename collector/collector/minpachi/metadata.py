"""みんパチ — 店舗メタデータ（旧イベント日など）"""

import re
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

DEFAULT_URL = "https://minpachi.com/%E3%82%AD%E3%82%B3%E3%83%BC%E3%83%8A%E5%B0%BC%E5%B4%8E%E6%9C%AC%E5%BA%97/"


async def fetch_store_metadata(url: str | None = None) -> dict[str, Any]:
    url = url or DEFAULT_URL
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        res = await client.get(url, headers={"User-Agent": USER_AGENT})
        res.raise_for_status()
        html = res.text

    event_days: list[int] = []
    if m := re.search(r"旧イベント日[^0-9]*([0-9、,/\s]+)", html):
        event_days = [int(x) for x in re.findall(r"\d", m.group(1)) if x.isdigit()]

    anniversary = None
    if m := re.search(r"周年[^0-9]*(\d{1,2})月(\d{1,2})日", html):
        anniversary = f"{m.group(1)}-{m.group(2)}"

    slot_count = None
    if m := re.search(r"スロット\s*(\d+)\s*台", html):
        slot_count = int(m.group(1))

    return {
        "event_days": sorted(set(event_days)),
        "anniversary": anniversary,
        "slot_count": slot_count,
        "source_url": url,
    }
