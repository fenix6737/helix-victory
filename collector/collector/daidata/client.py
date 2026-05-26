"""
台データオンライン Playwright クライアント。

プレミアム会員ログイン後の storage state を DAIDATA_STORAGE_STATE に保存して使用。
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from collector.daidata.parser import parse_all_list_html
from collector.daidata.retry import with_retry
from collector.daidata.session import DaidataSessionError, is_logged_in_html, validate_storage
from collector.daidata.stores import resolve_store

logger = logging.getLogger("daidata")

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def _shop_id_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.split("/")[0] if path else ""


async def _new_context(browser, storage_path: str | None):
    if storage_path and os.path.isfile(storage_path):
        return await browser.new_context(
            user_agent=MOBILE_UA,
            storage_state=storage_path,
            locale="ja-JP",
        )
    return await browser.new_context(user_agent=MOBILE_UA, locale="ja-JP")


async def _fetch_all_list_page_once(
    shop_id: str,
    hist_num: int,
    storage_path: str | None,
) -> str:
    if hist_num > 0:
        url = f"https://daidata.goraggio.com/{shop_id}/all_list?ps=S&hist_num={hist_num}"
    else:
        url = f"https://daidata.goraggio.com/{shop_id}/all_list?ps=S"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await _new_context(browser, storage_path)
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await page.wait_for_timeout(2000)
            try:
                await page.wait_for_selector("table.tablesorter tbody tr td", timeout=8000)
            except Exception:
                pass
            return await page.content()
        finally:
            await context.close()
            await browser.close()


async def fetch_all_list_page(
    shop_id: str,
    hist_num: int = 0,
    storage_path: str | None = None,
) -> str:
    html = await with_retry(
        lambda: _fetch_all_list_page_once(shop_id, hist_num, storage_path),
        label=f"all_list h={hist_num}",
    )
    if not is_logged_in_html(html):
        raise DaidataSessionError(
            f"daidata 未ログインまたはデータ取得失敗 (shop={shop_id} hist={hist_num})。"
            " scripts/daidata_login.py でセッションを更新してください。"
        )
    return html


async def scrape_daidata_store(
    helix_store_id: str,
    store_url: str,
    *,
    hist_days: int = 7,
    storage_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    店舗のスロット台一覧を取得（当日 + 過去 hist_days 日分の all_list）。
    """
    store = resolve_store(helix_store_id, store_url)
    shop_id = _shop_id_from_url(store_url) or (store.daidata_shop_id if store else "")
    if not shop_id:
        logger.error("店舗IDを解決できません: %s", helix_store_id)
        return []

    storage_path = storage_path or os.getenv("DAIDATA_STORAGE_STATE")
    try:
        validate_storage(storage_path)
    except DaidataSessionError as e:
        logger.error("[%s] %s", helix_store_id, e)
        return []

    all_rows: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # 当日（hist_num なし）
    html_today = await fetch_all_list_page(shop_id, 0, storage_path)
    rows_today = parse_all_list_html(html_today, helix_store_id, 0, now)
    if rows_today:
        all_rows.extend(rows_today)
        logger.info("[%s] today: %d rows", helix_store_id, len(rows_today))
    else:
        logger.warning(
            "[%s] 当日データ0件 — プレミアムログイン(storage state)または店舗契約を確認",
            helix_store_id,
        )

    # 過去日（hist_num 1..N）
    for h in range(1, min(hist_days + 1, 98)):
        html = await fetch_all_list_page(shop_id, h, storage_path)
        rows = parse_all_list_html(html, helix_store_id, h, now)
        if rows:
            all_rows.extend(rows)

    # 台詳細リンクから graph URL 補完（当日のみ・最大50台）
    if rows_today and storage_path:
        all_rows = await _enrich_graph_urls(shop_id, rows_today[:50], storage_path, all_rows)

    return all_rows


async def _enrich_graph_urls(
    shop_id: str,
    sample_rows: list[dict],
    storage_path: str,
    existing: list[dict],
) -> list[dict]:
    """個別台ページからグラフURLを補完（任意）"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await _new_context(browser, storage_path)
        page = await context.new_page()
        graph_by_num: dict[int, str] = {}
        try:
            for row in sample_rows:
                num = row["machine_number"]
                url = f"https://daidata.goraggio.com/{shop_id}/ps/{num}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    img = await page.query_selector("img[src*='graph'], img.slump, .graph img")
                    if img:
                        src = await img.get_attribute("src")
                        if src:
                            graph_by_num[num] = src
                except Exception:
                    continue
        finally:
            await context.close()
            await browser.close()

    if not graph_by_num:
        return existing

    for row in existing:
        g = graph_by_num.get(row.get("machine_number"))
        if g and not row.get("graph_url"):
            row["graph_url"] = g
    return existing


async def save_storage_state(
    email: str,
    password: str,
    out_path: str,
    *,
    auto: bool = False,
    headless: bool = False,
) -> None:
    """ログイン後 storage state を保存（auto=True で自動送信）"""
    import re
    from pathlib import Path

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(user_agent=MOBILE_UA)
        page = await context.new_page()
        await page.goto("https://daidata.goraggio.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        if email:
            for sel in ('input[type="email"]', 'input[name="email"]', "#email"):
                if await page.locator(sel).count():
                    await page.fill(sel, email)
                    break
        if password:
            for sel in ('input[type="password"]', 'input[name="password"]', "#password"):
                if await page.locator(sel).count():
                    await page.fill(sel, password)
                    break

        if auto and email and password:
            for sel in (
                'button[type="submit"]',
                'input[type="submit"]',
                "button:has-text('ログイン')",
                "button:has-text('Login')",
            ):
                if await page.locator(sel).count():
                    await page.locator(sel).first.click()
                    break
            try:
                await page.wait_for_url(re.compile(r"daidata\.goraggio\.com/(?!login)"), timeout=90000)
            except Exception:
                await page.wait_for_timeout(5000)
            html = await page.content()
            if not is_logged_in_html(html) and "login" in page.url.lower():
                await browser.close()
                raise DaidataSessionError(
                    "自動ログイン失敗 — CAPTCHA/2FA の場合は headless=False で手動ログイン"
                )
        else:
            logger.info("ブラウザでログイン完了後、Enterで storage state を保存...")
            input()

        await context.storage_state(path=out_path)
        await browser.close()
    logger.info("Saved: %s", out_path)
