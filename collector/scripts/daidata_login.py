"""台データオンラインにログインし storage state を保存する。

Usage:
  python scripts/daidata_login.py
  # → ブラウザが開くので手動ログイン後、ターミナルで Enter
"""

import asyncio
import os
import sys
from pathlib import Path

COLLECTOR_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = COLLECTOR_ROOT.parent
sys.path.insert(0, str(COLLECTOR_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from collector.daidata.client import save_storage_state


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="自動ログイン（メール/パスワード送信）")
    parser.add_argument("--headless", action="store_true", help="ヘッドレス")
    args = parser.parse_args()

    rel = os.getenv("DAIDATA_STORAGE_STATE", "collector/daidata_auth.json")
    out = rel if os.path.isabs(rel) else str(PROJECT_ROOT / rel)
    email = os.getenv("DAIDATA_EMAIL", "")
    password = os.getenv("DAIDATA_PASSWORD", "")
    if not email or not password:
        print("Set DAIDATA_EMAIL and DAIDATA_PASSWORD in .env")
        return
    await save_storage_state(
        email, password, out, auto=args.auto or os.getenv("DAIDATA_AUTO_LOGIN") == "1", headless=args.headless
    )


if __name__ == "__main__":
    asyncio.run(main())
