"""
高頻度データ収集ランナー。

通常: 1〜5分 / ピーク: 30秒〜1分
"""

import argparse
import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from collector.config import config
from collector.ingest_client import post_logs
from collector.scraper import scrape_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("collector")


async def collect_once(store_id: str) -> None:
    url = config.store_urls.get(store_id)
    if not url:
        logger.error("Unknown store: %s", store_id)
        return

    try:
        logs = await scrape_store(store_id, url)
    except Exception as e:
        logger.error("[%s] collect failed: %s", store_id, e)
        raise

    result = await post_logs(config.api_url, store_id, logs)
    logger.info("[%s] inserted=%s skipped=%s", store_id, result.get("inserted"), result.get("skipped"))


def schedule_store(scheduler: AsyncIOScheduler, store_id: str) -> None:
    def job():
        asyncio.create_task(collect_once(store_id))

    hour = datetime.now(timezone.utc).hour
    interval = config.interval_for_hour(hour)

    scheduler.add_job(
        job,
        "interval",
        seconds=interval,
        id=f"collect_{store_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Scheduled %s every %ds", store_id, interval)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", required=True, choices=list(config.store_urls.keys()))
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if args.once:
        await collect_once(args.store)
        return

    scheduler = AsyncIOScheduler()
    schedule_store(scheduler, args.store)
    scheduler.start()
    logger.info("Collector running for %s. Ctrl+C to stop.", args.store)
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
