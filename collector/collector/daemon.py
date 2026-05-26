"""
常駐コレクター — 全店舗スケジュール・失敗監視・バックオフ

使い方:
  python -m collector.daemon
  python -m collector.daemon --stores kicona_amagasaki,maruhan_umeda
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from collector.config import config
from collector.ingest_client import post_logs
from collector.ingest_queue import enqueue_failed, flush_queue
from collector.scraper import scrape_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [daemon] %(message)s",
)
logger = logging.getLogger("collector.daemon")

STATE_DIR = Path(os.getenv("COLLECTOR_STATE_DIR", "collector/state"))
STATE_FILE = STATE_DIR / "daemon_state.json"
DEFAULT_STORES = list(config.store_urls.keys())


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"stores": {}}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


async def collect_store(store_id: str, state: dict) -> None:
    url = config.store_urls.get(store_id)
    if not url:
        return

    st = state["stores"].setdefault(
        store_id,
        {"failures": 0, "backoff_until": None, "last_ok": None, "last_error": None},
    )

    max_failures = int(os.getenv("COLLECTOR_MAX_FAILURES", "12"))
    if int(st.get("failures", 0)) >= max_failures:
        logger.warning("[%s] dead source skip (failures>=%d)", store_id, max_failures)
        return

    backoff_until = st.get("backoff_until")
    if backoff_until:
        until = datetime.fromisoformat(backoff_until.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < until:
            logger.info("[%s] backoff until %s", store_id, backoff_until)
            return

    try:
        await flush_queue(config.api_url, store_id, max_batches=1)
        logs = await scrape_store(store_id, url)
        result = await post_logs(config.api_url, store_id, logs)
        st["failures"] = 0
        st["backoff_until"] = None
        st["last_ok"] = datetime.now(timezone.utc).isoformat()
        st["last_error"] = None
        logger.info(
            "[%s] ok inserted=%s skipped=%s rows=%d",
            store_id,
            result.get("inserted"),
            result.get("skipped"),
            len(logs),
        )
    except Exception as e:
        st["failures"] = int(st.get("failures", 0)) + 1
        st["last_error"] = str(e)[:500]
        pending = locals().get("logs")
        if pending:
            try:
                enqueue_failed(store_id, pending, str(e))
            except Exception:
                pass
        delay = min(3600, 60 * (2 ** min(st["failures"], 6)))
        until = datetime.now(timezone.utc).timestamp() + delay
        st["backoff_until"] = datetime.fromtimestamp(until, tz=timezone.utc).isoformat()
        logger.error("[%s] failed (#%d) backoff %ds: %s", store_id, st["failures"], delay, e)
        raise


def _schedule_store(scheduler: AsyncIOScheduler, store_id: str, state: dict) -> None:
    hour = datetime.now(timezone.utc).hour
    interval = config.interval_for_hour(hour)

    def job():
        asyncio.create_task(_job_wrapper(store_id, state))

    scheduler.add_job(
        job,
        "interval",
        seconds=interval,
        id=f"daemon_{store_id}",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("scheduled %s every %ds", store_id, interval)


async def _job_wrapper(store_id: str, state: dict) -> None:
    try:
        await collect_store(store_id, state)
    finally:
        _save_state(state)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stores",
        default=",".join(DEFAULT_STORES),
        help="Comma-separated store ids",
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    stores = [s.strip() for s in args.stores.split(",") if s.strip()]

    state = _load_state()

    if args.once:
        for sid in stores:
            await collect_store(sid, state)
        _save_state(state)
        return

    scheduler = AsyncIOScheduler()
    for sid in stores:
        _schedule_store(scheduler, sid, state)
    scheduler.start()
    _save_state(state)
    logger.info("Daemon running stores=%s Ctrl+C to stop", stores)

    try:
        tick = 0
        while True:
            await asyncio.sleep(60)
            tick += 1
            state["watchdog_tick"] = tick
            state["watchdog_at"] = datetime.now(timezone.utc).isoformat()
            for sid in stores:
                st = state["stores"].get(sid, {})
                if st.get("last_ok"):
                    st["stale_recovery"] = tick % 5 == 0
            _save_state(state)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        _save_state(state)


if __name__ == "__main__":
    asyncio.run(main())
