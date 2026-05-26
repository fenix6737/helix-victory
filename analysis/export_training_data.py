"""
PostgreSQL 生ログ → 学習用 CSV エクスポート。

Usage:
  python export_training_data.py maruhan_umeda output.csv
"""

import asyncio
import os
import sys

import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC", "postgresql://helix:helix@localhost:5432/helix_victory"
)


def export_store(store_id: str, out_path: str) -> int:
    engine = create_engine(DATABASE_URL)
    q = text(
        """
        SELECT
            r.machine_id,
            r.captured_at,
            r.diff_coins,
            r.rotation_count,
            r.big_count,
            r.reg_count,
            r.final_games,
            r.is_operating,
            m.position_type,
            m.island_id,
            m.machine_number,
            m.title
        FROM raw_logs r
        JOIN machines m ON m.id = r.machine_id
        WHERE r.store_id = :store_id
        ORDER BY r.captured_at
        """
    )
    with engine.connect() as conn:
        df = pd.read_sql(q, conn, params={"store_id": store_id})

    if df.empty:
        print("No data")
        return 0

    # 簡易ラベル: 店舗内日次差枚ランク（翌日相対パフォーマンス proxy）
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    df["date"] = df["captured_at"].dt.date
    daily = df.groupby(["date", "machine_id"])["diff_coins"].last().reset_index()
    daily["label"] = daily.groupby("date")["diff_coins"].rank(pct=True)

    merged = df.merge(daily[["date", "machine_id", "label"]], on=["date", "machine_id"], how="left")
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Exported {len(merged)} rows -> {out_path}")
    return len(merged)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_training_data.py <store_id> <output.csv>")
        sys.exit(1)
    export_store(sys.argv[1], sys.argv[2])
