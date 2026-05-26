import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

import httpx
from bs4 import BeautifulSoup
from collector.minrepo.client import _fetch, USER_AGENT

URL = "https://min-repo.com/pachinko/919512/?kishu=all"


async def main() -> None:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as c:
        html = await _fetch(c, URL)
    soup = BeautifulSoup(html, "lxml")
    for h2 in soup.find_all("h2"):
        if "全台" not in h2.get_text():
            continue
        print("h2:", repr(h2.get_text()))
        wrap = h2.find_next("div", class_="table_wrap")
        table = wrap.find("table") if wrap else h2.find_next("table")
        if not table:
            print("no table")
            continue
        for i, tr in enumerate(table.find_all("tr")[:5]):
            tds = tr.find_all("td")
            print(f"row{i} ntd={len(tds)}", [td.get_text(strip=True)[:15] for td in tds[:6]])


asyncio.run(main())
