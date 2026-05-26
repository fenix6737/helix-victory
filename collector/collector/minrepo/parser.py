"""みんレポ（min-repo.com）HTML パーサー — キコーナ尼崎本店"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup

from collector.game_type import classify_game_type

JST = timezone(timedelta(hours=9))


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("+", "")
    m = re.search(r"-?\d+", cleaned)
    return int(m.group()) if m else None


def report_url_from_id(post_id: str) -> str:
    return f"https://min-repo.com/{post_id.strip().rstrip('/')}/"


def parse_tag_report_links(html: str, limit: int = 14) -> list[dict[str, Any]]:
    """タグ一覧ページから日次レポートURLを抽出"""
    soup = BeautifulSoup(html, "lxml")
    reports: list[dict[str, Any]] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            link = tds[0].find("a", href=re.compile(r"min-repo\.com/\d+"))
            if not link:
                continue
            href = link.get("href", "")
            m = re.search(r"min-repo\.com/(\d+)", href)
            if not m:
                continue
            label = link.get_text(strip=True)
            reports.append(
                {
                    "post_id": m.group(1),
                    "url": href if href.startswith("http") else f"https://min-repo.com/{m.group(1)}/",
                    "label": label,
                }
            )

    # 重複除去（先頭が新しい）
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in reports:
        if r["post_id"] not in seen:
            seen.add(r["post_id"])
            unique.append(r)

    return unique[:limit]


def parse_report_datetime(html: str, fallback_label: str = "") -> datetime:
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", type="application/ld+json")
    if script and script.string:
        import json

        try:
            data = json.loads(script.string)
            if data.get("datePublished"):
                dt = datetime.fromisoformat(data["datePublished"].replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc)
        except (json.JSONDecodeError, ValueError):
            pass

    time_el = soup.find("time", class_="date")
    if time_el and time_el.get("datetime"):
        dt = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)

    # "3/26(木)" → 当年の日付 22:00 JST（営業終了想定）
    m = re.search(r"(\d{1,2})/(\d{1,2})", fallback_label)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        now = datetime.now(JST)
        year = now.year
        try:
            dt = datetime(year, month, day, 22, 0, tzinfo=JST)
            if dt > now:
                dt = datetime(year - 1, month, day, 22, 0, tzinfo=JST)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

    return datetime.now(timezone.utc)


def parse_all_machines(html: str, store_id: str, captured_at: datetime) -> list[dict[str, Any]]:
    """?kishu=all ページの全台テーブルをパース"""
    soup = BeautifulSoup(html, "lxml")
    rows_out: list[dict[str, Any]] = []

    for h2 in soup.find_all("h2"):
        if "全台" not in h2.get_text():
            continue
        wrap = h2.find_next("div", class_="table_wrap")
        if not wrap:
            wrap = h2.find_next("table")
        table = wrap.find("table") if wrap and wrap.name != "table" else wrap
        if not table:
            continue

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue

            title_el = tds[0].find("a") or tds[0]
            num_el = tds[1].find("a") or tds[1]
            title = title_el.get_text(strip=True)
            machine_number = _parse_int(num_el.get_text(strip=True))
            if machine_number is None or not title:
                continue

            # スロット: 機種・台番・差枚・G数 / パチンコ: 機種・台番・出玉系3列
            if len(tds) >= 4:
                diff_coins = _parse_int(tds[2].get_text(strip=True))
                final_games = _parse_int(tds[3].get_text(strip=True))
            else:
                diff_coins = _parse_int(tds[2].get_text(strip=True))
                final_games = None

            rows_out.append(
                {
                    "machine_number": machine_number,
                    "title": title,
                    "diff_coins": diff_coins,
                    "rotation_count": None,
                    "big_count": None,
                    "reg_count": None,
                    "final_games": final_games,
                    "graph_url": None,
                    "is_operating": diff_coins is not None,
                    "captured_at": captured_at.isoformat(),
                    "source": "minrepo",
                    "store_id": store_id,
                    "game_type": classify_game_type(title),
                }
            )
        break

    return rows_out
