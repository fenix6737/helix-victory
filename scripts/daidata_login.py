"""
台データオンライン — プレミアムログイン後 storage state 保存

  cd collector
  py -3.12 ../scripts/daidata_login.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from collector.daidata.client import save_storage_state


async def main() -> None:
    out = os.getenv("DAIDATA_STORAGE_STATE", str(ROOT / "collector" / "daidata_auth.json"))
    email = os.getenv("DAIDATA_EMAIL", "")
    password = os.getenv("DAIDATA_PASSWORD", "")
    await save_storage_state(email, password, out)


if __name__ == "__main__":
    asyncio.run(main())
