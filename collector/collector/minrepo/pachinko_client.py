"""みんレポ パチンコ版 — キコーナ尼崎本店"""

import logging
import os
import re
from typing import Any

import httpx

from collector.minrepo.client import USER_AGENT, _fetch, scrape_report_url
from collector.minrepo.parser import parse_all_machines, parse_report_datetime, parse_tag_report_links

logger = logging.getLogger("minrepo.pachinko")

PACHINKO_TAG_DEFAULT = (
    "https://min-repo.com/pachinko/tag/%e3%82%ad%e3%82%b3%e3%83%bc%e3%83%8a%e5%b0%bc%e5%b4%8e%e6%9c%ac%e5%ba%97/"
)


def _normalize_pachinko_url(href: str, post_id: str) -> str:
    if href.startswith("http"):
        if "/pachinko/" in href:
            return href if href.endswith("/") else href + "/"
        return f"https://min-repo.com/pachinko/{post_id}/"
    if href.startswith("/pachinko/"):
        return f"https://min-repo.com{href}" if href.endswith("/") else f"https://min-repo.com{href}/"
    return f"https://min-repo.com/pachinko/{post_id}/"


def parse_pachinko_tag_links(html: str, limit: int = 14) -> list[dict[str, Any]]:
    """パチンコ版タグ一覧からレポートURL"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    reports: list[dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/pachinko/(\d+)/?", href) or re.search(r"min-repo\.com/(\d+)", href)
        if not m:
            continue
        post_id = m.group(1)
        reports.append(
            {
                "post_id": post_id,
                "url": _normalize_pachinko_url(href, post_id),
                "label": a.get_text(strip=True),
            }
        )

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in reports:
        if r["post_id"] not in seen:
            seen.add(r["post_id"])
            unique.append(r)
    return unique[:limit]


async def scrape_minrepo_pachinko(
    store_id: str,
    tag_url: str | None = None,
    *,
    hist_days: int | None = None,
) -> list[dict[str, Any]]:
    tag_url = tag_url or os.getenv("MINREPO_PACHINKO_TAG_URL", PACHINKO_TAG_DEFAULT)
    hist_days = hist_days if hist_days is not None else int(os.getenv("MINREPO_PACHINKO_HIST_DAYS", "7"))

    all_rows: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        tag_html = await _fetch(client, tag_url)
        reports = parse_pachinko_tag_links(tag_html, limit=hist_days)

        if not reports:
            logger.warning("[%s] pachinko tag: 0 reports from %s", store_id, tag_url)
            return []

        logger.info("[%s] pachinko: %d reports", store_id, len(reports))

        for report in reports:
            post_id = report["post_id"]
            base = report["url"].rstrip("/")
            try:
                report_html = await _fetch(client, base + "/")
                captured_at = parse_report_datetime(report_html, report.get("label", ""))
                all_html = await _fetch(client, f"{base}/?kishu=all")
                rows = parse_all_machines(all_html, store_id, captured_at)
            except Exception:
                rows = await scrape_report_url(store_id, base, client)

            for row in rows:
                row["game_type"] = "pachinko"
                row["source"] = "minrepo_pachinko"

            if rows:
                logger.info(
                    "[%s] pachinko post=%s: %d machines",
                    store_id,
                    post_id,
                    len(rows),
                )
                all_rows.extend(rows)

    return all_rows
