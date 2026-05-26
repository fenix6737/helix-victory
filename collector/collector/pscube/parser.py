"""PS Cube（出玉情報）HTML パーサー"""

import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from collector.game_type import classify_game_type


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("+", "")
    m = re.search(r"-?\d+", cleaned)
    return int(m.group()) if m else None


def parse_pscube_machines(html: str, store_id: str) -> list[dict[str, Any]]:
    """
    台番・機種名・差枚などをテーブル/リストから抽出。
    サイト構造変更時も正規表現フォールバックで可能な限り拾う。
    """
    soup = BeautifulSoup(html, "lxml")
    captured_at = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add_row(num: int, title: str, diff: int | None, bb: int | None, rb: int | None) -> None:
        if num in seen or num <= 0:
            return
        seen.add(num)
        rows.append(
            {
                "store_id": store_id,
                "machine_number": num,
                "title": title[:128] if title else f"台{num}",
                "captured_at": captured_at.isoformat(),
                "diff_coins": diff,
                "big_count": bb,
                "reg_count": rb,
                "source": "pscube",
                "game_type": classify_game_type(title),
            }
        )

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            num = _parse_int(cells[0])
            if num is None or num > 9999:
                continue
            title = cells[1] if len(cells) > 1 else ""
            if not title or title in ("台番", "機種", "台番号"):
                continue
            diff = _parse_int(cells[2]) if len(cells) > 2 else None
            bb = _parse_int(cells[3]) if len(cells) > 3 else None
            rb = _parse_int(cells[4]) if len(cells) > 4 else None
            add_row(num, title, diff, bb, rb)

    for block in soup.find_all(string=re.compile(r"台番|台No|台\s*\d+")):
        parent = block.parent
        if not parent:
            continue
        text = parent.get_text(" ", strip=True)
        m_num = re.search(r"(?:台番|台No\.?|台)\s*[:#]?\s*(\d{1,4})", text)
        if not m_num:
            continue
        num = int(m_num.group(1))
        m_title = re.search(r"(?:機種|タイトル)[:：]?\s*(.+?)(?:\s+差枚|\s+BB|$)", text)
        title = m_title.group(1).strip() if m_title else f"台{num}"
        m_diff = re.search(r"差枚[:：]?\s*([+-]?\d+)", text)
        diff = int(m_diff.group(1)) if m_diff else None
        add_row(num, title, diff, None, None)

    return rows
