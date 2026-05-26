"""
キコーナ尼崎本店 — 複合データソース（本番）

1. アナスロ: 全台・BB/RB・差枚・G数（高密度）
2. みんレポ: 日次レポート補完・最新レポート直リンク対応
3. みんパチ: 旧イベント日メタデータ → APIへ送信
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from collector.anaslo.client import scrape_anaslo_store
from collector.hallnavi.client import fetch_hall_navi_info
from collector.minpachi.metadata import fetch_store_metadata
from collector.minrepo.client import scrape_minrepo_store
from collector.minrepo.pachinko_client import scrape_minrepo_pachinko
from collector.pscube.client import scrape_pscube_store

logger = logging.getLogger("kicona")

STORE_ID = "kicona_amagasaki"


def _merge_rows(rows_list: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """同一 (日付, 台番) は anaslo 優先（BB/RBあり）"""
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    priority = {"anaslo": 4, "pscube": 3, "minrepo": 2, "minrepo_pachinko": 2}

    for rows in rows_list:
        for row in rows:
            captured = row.get("captured_at", "")[:10]
            key = (captured, int(row["machine_number"]))
            src = row.get("source", "minrepo")
            existing = merged.get(key)
            if not existing or priority.get(src, 0) >= priority.get(existing.get("source", ""), 0):
                merged[key] = row
    return list(merged.values())


async def _post_metadata(api_url: str, metadata: dict[str, Any]) -> None:
    """店舗メタデータを API へ送信（データソース状態を含む）"""
    api_key = os.getenv("INGEST_API_KEY", "")
    headers = {"X-Ingest-Key": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"{api_url}/api/v1/stores/{STORE_ID}/metadata",
            json=metadata,
            headers=headers,
        )


async def scrape_kicona_amagasaki(
    store_id: str = STORE_ID,
    *,
    api_url: str | None = None,
) -> list[dict[str, Any]]:
    batches: list[list[dict[str, Any]]] = []
    errors: list[str] = []
    source_status: dict[str, Any] = {}

    # アナスロ（主データ源）
    try:
        anaslo_rows = await scrape_anaslo_store(store_id)
        batches.append(anaslo_rows)
        source_status["anaslo"] = {"ok": True, "row_count": len(anaslo_rows)}
    except Exception as e:
        errors.append(f"anaslo: {e}")
        source_status["anaslo"] = {"ok": False, "error": str(e)}
        logger.error("[%s] anaslo failed: %s", store_id, e)

    # PS Cube（出玉情報）
    try:
        pscube_rows, pscube_st = await scrape_pscube_store(store_id)
        source_status["pscube"] = pscube_st
        if pscube_rows:
            batches.append(pscube_rows)
    except Exception as e:
        source_status["pscube"] = {"ok": False, "error": str(e)}
        logger.warning("[%s] pscube failed: %s", store_id, e)

    # みんレポ（補完 + ユーザー指定レポート）
    try:
        minrepo_rows = await scrape_minrepo_store(
            store_id,
            latest_report_url=os.getenv(
                "MINREPO_LATEST_REPORT_URL",
                "https://min-repo.com/3093761/",
            ),
        )
        batches.append(minrepo_rows)
        source_status["minrepo"] = {"ok": True, "row_count": len(minrepo_rows)}
    except Exception as e:
        errors.append(f"minrepo: {e}")
        source_status["minrepo"] = {"ok": False, "error": str(e)}
        logger.warning("[%s] minrepo failed: %s", store_id, e)

    try:
        pachinko_rows = await scrape_minrepo_pachinko(store_id)
        if pachinko_rows:
            batches.append(pachinko_rows)
            logger.info("[%s] minrepo pachinko: %d rows", store_id, len(pachinko_rows))
    except Exception as e:
        logger.warning("[%s] minrepo pachinko failed: %s", store_id, e)

    if not batches:
        raise RuntimeError(
            f"[{store_id}] 全ソース失敗: " + "; ".join(errors)
        )

    merged = _merge_rows(batches)
    logger.info(
        "[%s] merged %d rows (anaslo+minrepo)",
        store_id,
        len(merged),
    )

    # ホールナビ + みんパチメタデータ
    if api_url:
        hall_st = await fetch_hall_navi_info(store_id)
        source_status["hall_navi"] = hall_st
        meta_payload: dict[str, Any] = {
            "data_sources": source_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            minpachi = await fetch_store_metadata(os.getenv("MINPACHI_STORE_URL"))
            meta_payload.update(minpachi)
            source_status["minpachi"] = {"ok": True}
        except Exception as e:
            source_status["minpachi"] = {"ok": False, "error": str(e)}
            logger.warning("[%s] minpachi metadata skip: %s", store_id, e)
        if hall_st.get("info"):
            meta_payload["hall_navi"] = hall_st["info"]
        await _post_metadata(api_url, meta_payload)
        logger.info("[%s] metadata posted sources=%s", store_id, list(source_status.keys()))

    return merged
