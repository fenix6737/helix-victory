"""
みんレポ収集クライアント — キコーナ尼崎本店（兵庫県尼崎市神田中通2-27-29）

台データオンラインに未掲載のため、公開されている差枚レポートを収集する。
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from collector.minrepo.parser import (
    parse_all_machines,
    parse_report_datetime,
    parse_tag_report_links,
)

logger = logging.getLogger("minrepo")

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

TAG_URL_DEFAULT = (
    "https://min-repo.com/tag/%e3%82%ad%e3%82%b3%e3%83%bc%e3%83%8a%e5%b0%bc%e5%b4%8e%e6%9c%ac%e5%ba%97/"
)


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    res = await client.get(url, headers={"User-Agent": USER_AGENT})
    res.raise_for_status()
    return res.text


async def scrape_report_url(
    store_id: str,
    report_url: str,
    client: httpx.AsyncClient,
) -> list[dict[str, Any]]:
    report_url = report_url.rstrip("/") + "/"
    report_html = await _fetch(client, report_url)
    m = re.search(r"min-repo\.com/(\d+)", report_url)
    label = m.group(1) if m else ""
    captured_at = parse_report_datetime(report_html, label)
    all_html = await _fetch(client, f"{report_url}?kishu=all")
    return parse_all_machines(all_html, store_id, captured_at)


async def scrape_minrepo_store(
    store_id: str,
    tag_url: str | None = None,
    *,
    hist_days: int | None = None,
    latest_report_url: str | None = None,
) -> list[dict[str, Any]]:
    tag_url = tag_url or os.getenv(
        "MINREPO_TAG_URL",
        os.getenv("KICONA_AMAGASAKI_URL", TAG_URL_DEFAULT),
    )
    hist_days = hist_days if hist_days is not None else int(os.getenv("MINREPO_HIST_DAYS", "7"))
    latest_report_url = latest_report_url or os.getenv("MINREPO_LATEST_REPORT_URL")

    all_rows: list[dict[str, Any]] = []
    seen_posts: set[str] = set()

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        if latest_report_url:
            rows = await scrape_report_url(store_id, latest_report_url, client)
            if rows:
                m = re.search(r"/(\d+)/", latest_report_url)
                if m:
                    seen_posts.add(m.group(1))
                logger.info("[%s] minrepo latest: %d rows", store_id, len(rows))
                all_rows.extend(rows)

        tag_html = await _fetch(client, tag_url)
        reports = parse_tag_report_links(tag_html, limit=hist_days)

        if not reports:
            raise RuntimeError(
                f"[{store_id}] みんレポにレポートが見つかりません: {tag_url}"
            )

        logger.info("[%s] %d reports from min-repo tag page", store_id, len(reports))

        for report in reports:
            if report["post_id"] in seen_posts:
                continue
            report_url = report["url"].rstrip("/")
            all_url = f"{report_url}/?kishu=all"

            report_html = await _fetch(client, report_url + "/")
            captured_at = parse_report_datetime(report_html, report.get("label", ""))

            all_html = await _fetch(client, all_url)
            rows = parse_all_machines(all_html, store_id, captured_at)

            if not rows:
                logger.warning(
                    "[%s] 全台0件 post=%s — ページ構造変更の可能性",
                    store_id,
                    report["post_id"],
                )
                continue

            logger.info(
                "[%s] post=%s (%s): %d machines",
                store_id,
                report["post_id"],
                report.get("label"),
                len(rows),
            )
            all_rows.extend(rows)

    if not all_rows:
        raise RuntimeError(
            f"[{store_id}] みんレポから台データを取得できませんでした。"
            " tag URL・ネットワーク・HTML構造を確認してください。"
        )

    return all_rows
