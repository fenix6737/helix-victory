"""ingest キュー — 失敗時再送・重複ガード"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from collector.ingest_client import post_logs

logger = logging.getLogger("ingest_queue")

QUEUE_DIR = Path(__file__).resolve().parents[1] / "state" / "ingest_queue"


def _queue_path(store_id: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    return QUEUE_DIR / f"{store_id}.jsonl"


def enqueue_failed(store_id: str, logs: list[dict], error: str) -> None:
    path = _queue_path(store_id)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "error": error[:300],
        "count": len(logs),
        "logs": logs[:500],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.warning("[%s] queued %d logs for retry", store_id, len(logs))


async def flush_queue(api_url: str, store_id: str, max_batches: int = 3) -> int:
    path = _queue_path(store_id)
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        return 0
    flushed = 0
    remaining: list[str] = []
    for line in lines[:max_batches]:
        try:
            entry = json.loads(line)
            logs = entry.get("logs", [])
            if logs:
                await post_logs(api_url, store_id, logs)
                flushed += 1
        except Exception as e:
            logger.error("[%s] queue flush failed: %s", store_id, e)
            remaining.append(line)
    remaining.extend(lines[max_batches:])
    if remaining:
        path.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return flushed
