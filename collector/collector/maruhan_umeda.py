"""
マルハン梅田 — 複合データソース（P-WORLD/Site777/アナスロ/みんレポ）

優先: daidata(Site777) > anaslo > minrepo
source failover: 1源失敗でも他源で継続
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from collector.daidata.client import scrape_daidata_store
from collector.anaslo.client import scrape_anaslo_store
from collector.minrepo.client import scrape_minrepo_store
from collector.minrepo.pachinko_client import scrape_minrepo_pachinko

logger = logging.getLogger("maruhan_umeda")

STORE_ID = "maruhan_umeda"


def _merge_rows(rows_list: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    priority = {"daidata": 4, "anaslo": 3, "minrepo": 2, "minrepo_pachinko": 2}

    for rows in rows_list:
        for row in rows:
            captured = str(row.get("captured_at", ""))[:10]
            key = (captured, int(row["machine_number"]))
            src = row.get("source", "unknown")
            ex = merged.get(key)
            if not ex or priority.get(src, 0) >= priority.get(ex.get("source", ""), 0):
                merged[key] = row
    return list(merged.values())


def _dedupe_logs(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str]] = set()
    out: list[dict[str, Any]] = []
    for row in logs:
        cap = str(row.get("captured_at", ""))[:19]
        num = int(row["machine_number"])
        src = row.get("source", "")
        key = (cap, num, src)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


async def scrape_maruhan_umeda(
    store_id: str = STORE_ID,
    *,
    daidata_url: str | None = None,
    api_url: str | None = None,
) -> list[dict[str, Any]]:
    batches: list[list[dict[str, Any]]] = []
    errors: list[str] = []
    url = daidata_url or os.getenv("MARUHAN_UMEDA_URL", "https://daidata.goraggio.com/207042")

    try:
        dd = await scrape_daidata_store(
            store_id,
            url,
            hist_days=int(os.getenv("DAIDATA_HIST_DAYS", "7")),
        )
        for r in dd:
            r["source"] = "daidata"
        batches.append(dd)
        logger.info("[%s] daidata: %d rows", store_id, len(dd))
    except Exception as e:
        errors.append(f"daidata: {e}")
        logger.warning("[%s] daidata failed: %s", store_id, e)

    anaslo_url = os.getenv(
        "ANASLO_MARUHAN_LIST_URL",
        "https://ana-slo.com/%E3%83%9B%E3%83%BC%E3%83%AB%E3%83%87%E3%83%BC%E3%82%BF/"
        "%E5%A4%A7%E9%98%AA%E5%BA%9C/%E3%83%9E%E3%83%AB%E3%83%8F%E3%83%B3%E6%A2%85%E7%94%B0%E5%BA%97-%E3%83%87%E3%83%BC%E3%82%BF%E4%B8%80%E8%A6%A7/",
    )
    try:
        ar = await scrape_anaslo_store(store_id, anaslo_url, hist_days=3)
        batches.append(ar)
        logger.info("[%s] anaslo: %d rows", store_id, len(ar))
    except Exception as e:
        errors.append(f"anaslo: {e}")
        logger.warning("[%s] anaslo failed: %s", store_id, e)

    minrepo_url = os.getenv("MINREPO_MARUHAN_URL", "")
    if minrepo_url:
        try:
            mr = await scrape_minrepo_store(store_id, latest_report_url=minrepo_url)
            batches.append(mr)
        except Exception as e:
            errors.append(f"minrepo: {e}")

    try:
        pr = await scrape_minrepo_pachinko(
            store_id,
            tag_url=os.getenv("MINREPO_MARUHAN_PACHINKO_URL"),
        )
        if pr:
            batches.append(pr)
    except Exception as e:
        logger.debug("[%s] minrepo pachinko skip: %s", store_id, e)

    if not batches:
        raise RuntimeError(f"[{store_id}] 全ソース失敗: " + "; ".join(errors))

    merged = _dedupe_logs(_merge_rows(batches))
    logger.info("[%s] merged %d rows (failover ok, errors=%d)", store_id, len(merged), len(errors))

    if api_url and errors:
        try:
            api_key = os.getenv("INGEST_API_KEY", "")
            headers = {"X-Ingest-Key": api_key} if api_key else {}
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{api_url}/api/v1/stores/{store_id}/metadata",
                    json={"collector_warnings": errors[:5]},
                    headers=headers,
                )
        except Exception:
            pass

    return merged
