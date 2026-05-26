"""
店舗別データソースに応じた収集ディスパッチャ。
"""

import logging
import os
from typing import Any

from collector.config import config
from collector.daidata.client import scrape_daidata_store
from collector.kicona import scrape_kicona_amagasaki
from collector.maruhan_umeda import scrape_maruhan_umeda
from collector.sources import DataSource, get_store_config

logger = logging.getLogger("scraper")


async def scrape_store(store_id: str, url: str) -> list[dict[str, Any]]:
    cfg = get_store_config(store_id, url)
    if not cfg:
        raise ValueError(f"未知の店舗ID: {store_id}")

    if cfg.source == DataSource.DAIDATA:
        rows = await scrape_daidata_store(
            store_id,
            cfg.url,
            hist_days=int(os.getenv("DAIDATA_HIST_DAYS", "7")),
        )
    elif cfg.source == DataSource.KICONA_MULTI:
        rows = await scrape_kicona_amagasaki(store_id, api_url=config.api_url)
    elif cfg.source == DataSource.MARUHAN_MULTI:
        rows = await scrape_maruhan_umeda(store_id, daidata_url=cfg.url, api_url=config.api_url)
    else:
        raise ValueError(f"未対応ソース: {cfg.source}")

    if not rows:
        msg = (
            f"[{store_id}] 収集0件 ({cfg.source.value})。"
            " URL・認証・ネットワークを確認してください。"
        )
        if os.getenv("HELIX_LENIENT_COLLECT", "").lower() in ("1", "true", "yes"):
            logger.warning(msg)
            return []
        raise RuntimeError(msg)

    logger.info("[%s] collected %d rows via %s", store_id, len(rows), cfg.source.value)
    return rows
