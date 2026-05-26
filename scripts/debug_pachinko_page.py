import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

import httpx
from collector.minrepo.client import _fetch, USER_AGENT
from collector.minrepo.parser import parse_all_machines, parse_report_datetime

URL = "https://min-repo.com/pachinko/919512/"


async def main() -> None:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as c:
        report = await _fetch(c, URL)
        allp = await _fetch(c, URL + "?kishu=all")
        print("report len", len(report), "all len", len(allp))
        print("全台 in report", "全台" in report)
        print("全台 in all", "全台" in allp)
        cap = parse_report_datetime(report, "5/13")
        rows = parse_all_machines(allp, "kicona_amagasaki", cap)
        print("parse_all_machines", len(rows))
        if not rows:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(allp, "lxml")
            h2s = [h.get_text(strip=True)[:20] for h in soup.find_all("h2")[:8]]
            print("h2s", h2s)
            tables = soup.find_all("table")
            print("tables", len(tables))


asyncio.run(main())
