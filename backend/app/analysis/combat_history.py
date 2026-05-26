"""実戦ログ — combat_history.db（未来学習の核）"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = Path(os.getenv("COMBAT_HISTORY_DB", str(ROOT / "data" / "combat_history.db")))


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.execute(
        """CREATE TABLE IF NOT EXISTS combat_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id TEXT NOT NULL,
            target_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )"""
    )
    c.execute(
        "CREATE INDEX IF NOT EXISTS ix_combat_store_date ON combat_snapshots(store_id, target_date)"
    )
    return c


def save_combat_snapshot(
    store_id: str,
    target_date: date,
    payload: dict,
) -> None:
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO combat_snapshots (store_id, target_date, created_at, payload_json) VALUES (?,?,?,?)",
            (
                store_id,
                target_date.isoformat(),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(payload, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_snapshots(store_id: str, limit: int = 30) -> list[dict]:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT target_date, created_at, payload_json FROM combat_snapshots WHERE store_id=? ORDER BY id DESC LIMIT ?",
            (store_id, limit),
        ).fetchall()
        return [
            {"target_date": r[0], "created_at": r[1], "payload": json.loads(r[2])}
            for r in rows
        ]
    finally:
        conn.close()
