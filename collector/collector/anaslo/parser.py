"""アナスロ（ana-slo.com）HTMLパーサー"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup

from collector.game_type import classify_game_type

JST = timezone(timedelta(hours=9))


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("–", "").replace("-", "").replace("+", "")
    if not cleaned or cleaned in ("-", "–"):
        return None
    m = re.search(r"-?\d+", cleaned)
    return int(m.group()) if m else None


def parse_listing_day_links(html: str, limit: int = 14) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    days: list[dict[str, Any]] = []

    for row in soup.select(".date-table .table-row"):
        cells = row.select(".table-data-cell")
        if len(cells) < 2:
            continue
        link = cells[0].find("a", href=True)
        if not link:
            continue
        href = link["href"]
        if "-data" not in href and "/data/" not in href:
            continue
        if not href.startswith("http"):
            href = f"https://ana-slo.com{href}" if href.startswith("/") else f"https://ana-slo.com/{href}"
        label = link.get_text(strip=True)
        total_diff = _parse_int(cells[1].get_text()) if len(cells) > 1 else None
        avg_g = _parse_int(cells[3].get_text()) if len(cells) > 3 else None

        m = re.search(r"/(\d{4}-\d{2}-\d{2})-", href)
        day_str = m.group(1) if m else None

        days.append(
            {
                "url": href,
                "label": label,
                "date": day_str,
                "total_diff": total_diff,
                "avg_g": avg_g,
            }
        )

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for d in days:
        key = d.get("date") or d["url"]
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique[:limit]


def parse_day_machines(html: str, store_id: str, captured_at: datetime) -> list[dict[str, Any]]:
    """fixed_get_medals_table / all_data_table から全台データ"""
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_=re.compile(r"fixed_get_medals_table"))
    if not tables:
        tables = soup.find_all("table", id="all_data_table")

    rows_out: list[dict[str, Any]] = []

    for table in tables:
        header_map: dict[str, int] = {}
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            texts = [c.get_text(strip=True) for c in cells]

            if tr.find("th"):
                for i, h in enumerate(texts):
                    if "台番" in h or h == "台":
                        header_map["machine_number"] = i
                    elif "機種" in h:
                        header_map["title"] = i
                    elif h in ("G数", "Ｇ数", "G"):
                        header_map["final_games"] = i
                    elif "差枚" in h or "差" == h:
                        header_map["diff_coins"] = i
                    elif h.upper() == "BB":
                        header_map["big_count"] = i
                    elif h.upper() == "RB":
                        header_map["reg_count"] = i
                    elif "回転" in h or h in ("総回", "総回転"):
                        header_map["rotation_count"] = i
                continue

            if not header_map.get("machine_number") and len(texts) < 4:
                continue

            def cell(key: str) -> str:
                idx = header_map.get(key)
                return texts[idx] if idx is not None and idx < len(texts) else ""

            machine_number = _parse_int(cell("machine_number"))
            if machine_number is None and len(texts) >= 2:
                machine_number = _parse_int(texts[1])
            if machine_number is None:
                continue

            title = cell("title") or (texts[0] if texts else "不明")
            diff_coins = _parse_int(cell("diff_coins"))
            if diff_coins is None and len(texts) >= 4:
                diff_coins = _parse_int(texts[3])

            rows_out.append(
                {
                    "machine_number": machine_number,
                    "title": title,
                    "diff_coins": diff_coins,
                    "rotation_count": _parse_int(cell("rotation_count")),
                    "big_count": _parse_int(cell("big_count")),
                    "reg_count": _parse_int(cell("reg_count")),
                    "final_games": _parse_int(cell("final_games")),
                    "graph_url": None,
                    "is_operating": diff_coins is not None,
                    "captured_at": captured_at.isoformat(),
                    "source": "anaslo",
                    "store_id": store_id,
                    "game_type": classify_game_type(title),
                }
            )

    return rows_out


def day_captured_at(date_str: str, hour: int = 22) -> datetime:
    y, m, d = map(int, date_str.split("-"))
    return datetime(y, m, d, hour, 0, tzinfo=JST).astimezone(timezone.utc)
