"""みんレポパチンコ収集の疎通確認"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from collector.minrepo.client import _fetch
from collector.minrepo.pachinko_client import (
    PACHINKO_TAG_DEFAULT,
    parse_pachinko_tag_links,
    scrape_minrepo_pachinko,
)
import httpx


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        html = await _fetch(client, PACHINKO_TAG_DEFAULT)
        links = parse_pachinko_tag_links(html, limit=3)
        print(f"tag html={len(html)} links={len(links)}")
        for L in links[:2]:
            print(" ", L["url"], L.get("label", "")[:40])

    rows = await scrape_minrepo_pachinko("kicona_amagasaki")
    print(f"rows={len(rows)}")
    if rows:
        r = rows[0]
        print("sample", r["machine_number"], r["title"][:30], r["game_type"])


if __name__ == "__main__":
    asyncio.run(main())
