"""
アナスロ収集 — キコーナ尼崎本店

一覧 → 日別リンククリック（probe_anaslo.py と同手順）
"""

import logging
import os
from typing import Any
from urllib.parse import urljoin

from playwright.async_api import async_playwright

from collector.anaslo.parser import (
    day_captured_at,
    parse_day_machines,
    parse_listing_day_links,
)

logger = logging.getLogger("anaslo")

LIST_URL_DEFAULT = (
    "https://ana-slo.com/%E3%83%9B%E3%83%BC%E3%83%AB%E3%83%87%E3%83%BC%E3%82%BF/"
    "%E5%85%B5%E5%BA%AB%E7%9C%8C/%E3%82%AD%E3%82%B3%E3%83%BC%E3%83%8A%E5%B0%BC%E5%B4%8E%E6%9C%AC%E5%BA%97-%E3%83%87%E3%83%BC%E3%82%BF%E4%B8%80%E8%A6%A7/"
)

BASE = "https://ana-slo.com"


def _normalize_day_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(BASE, href)


async def scrape_anaslo_store(
    store_id: str,
    listing_url: str | None = None,
    *,
    hist_days: int | None = None,
) -> list[dict[str, Any]]:
    listing_url = listing_url or os.getenv("ANASLO_KICONA_LIST_URL", LIST_URL_DEFAULT)
    hist_days = hist_days if hist_days is not None else int(os.getenv("ANASLO_HIST_DAYS", "7"))

    all_rows: list[dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="ja-JP")
        page = await ctx.new_page()

        await page.goto(listing_url, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)
        listing_html = await page.content()
        days = parse_listing_day_links(listing_html, limit=hist_days)

        if not days:
            await browser.close()
            raise RuntimeError(f"[{store_id}] アナスロ一覧から日付リンクを取得できませんでした")

        for d in days:
            d["url"] = _normalize_day_url(d["url"])

        logger.info("[%s] anaslo: %d day links", store_id, len(days))

        for day in days:
            date_str = day.get("date")
            if not date_str:
                continue

            await page.goto(listing_url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(8000)

            link = page.locator(f'a[href*="{date_str}"][href*="data"]').first
            if await link.count() == 0:
                logger.warning("[%s] skip %s: link not found", store_id, date_str)
                continue

            for attempt in range(2):
                await link.click()
                await page.wait_for_timeout(15000)
                if "google_vignette" not in page.url:
                    break
                if attempt == 0:
                    logger.warning("[%s] %s: ad redirect, retry click", store_id, date_str)
                    await page.goto(listing_url, wait_until="domcontentloaded", timeout=90000)
                    await page.wait_for_timeout(5000)
                    link = page.locator(f'a[href*="{date_str}"][href*="data"]').first

            day_html = await page.content()
            captured = day_captured_at(date_str)
            rows = parse_day_machines(day_html, store_id, captured)
            if rows:
                logger.info("[%s] anaslo %s: %d machines", store_id, date_str, len(rows))
                all_rows.extend(rows)
            else:
                logger.warning(
                    "[%s] anaslo %s: 0 machines url=%s len=%d",
                    store_id,
                    date_str,
                    page.url,
                    len(day_html),
                )

        await browser.close()

    if not all_rows:
        raise RuntimeError(f"[{store_id}] アナスロから台データを取得できませんでした")

    return all_rows
