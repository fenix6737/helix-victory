"""
台データオンライン HTML パーサー。

参考URL: https://daidata.goraggio.com/{shop_id}/all_list?ps=S&hist_num={n}
テーブル class=tablesorter（列は店舗により多少異なる）
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from bs4 import BeautifulSoup


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d\-+,]", "", text.replace(",", ""))
    if not cleaned or cleaned in ("-", "+"):
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _header_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for i, h in enumerate(headers):
        h = h.strip()
        if "台番" in h or h == "台":
            mapping["machine_number"] = i
        elif "機種" in h:
            mapping["title"] = i
        elif "差枚" in h or "スランプ" in h:
            mapping["diff_coins"] = i
        elif "回転" in h or "スタート" in h:
            mapping["rotation_count"] = i
        elif "BB" in h.upper() or "BIG" in h.upper():
            mapping["big_count"] = i
        elif "RB" in h.upper() or "REG" in h.upper():
            mapping["reg_count"] = i
        elif "最終" in h and ("G" in h or "ゲーム" in h):
            mapping["final_games"] = i
        elif "貸玉" in h:
            mapping["rate"] = i
    return mapping


def _infer_cols_from_row(cells: list[str]) -> dict[str, Any]:
    """ヘッダーなし時の7列レイアウト（note.com 事例ベース）"""
    if len(cells) < 5:
        return {}
    # 典型: ['', 台番, 貸玉, 機種, BB, RB, スタート/差枚]
    out: dict[str, Any] = {}
    nums = [_parse_int(c) for c in cells]
    if len(cells) >= 7:
        out["machine_number"] = nums[1]
        out["title"] = cells[3].strip()
        out["big_count"] = nums[4]
        out["reg_count"] = nums[5]
        rot = nums[6]
        out["rotation_count"] = rot
        # 7列目が差枚の店舗もある
        if rot is not None and abs(rot) > 50000:
            out["diff_coins"] = rot
            out["rotation_count"] = None
    elif len(cells) >= 5:
        out["machine_number"] = nums[0] if nums[0] else nums[1]
        out["title"] = cells[2].strip() if len(cells) > 2 else ""
        out["big_count"] = nums[-3] if len(nums) >= 3 else None
        out["reg_count"] = nums[-2] if len(nums) >= 2 else None
        out["rotation_count"] = nums[-1]
    return out


def parse_all_list_html(
    html: str,
    store_id: str,
    hist_num: int = 0,
    captured_at: datetime | None = None,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_=re.compile(r"tablesorter|sorter"))
    if not tables:
        tables = soup.find_all("table", class_="detailTable")

    if not tables:
        return []

    captured = captured_at or datetime.now(timezone.utc)
    if hist_num > 0:
        captured = captured - timedelta(days=hist_num - 1)

    rows_out: list[dict[str, Any]] = []

    for table in tables:
        headers: list[str] = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
        col_map = _header_map(headers) if headers else {}

        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            cells = [td.get_text(strip=True) for td in tds]
            if not any(cells):
                continue

            if col_map:
                def cell(key: str) -> str:
                    idx = col_map.get(key)
                    return cells[idx] if idx is not None and idx < len(cells) else ""

                machine_number = _parse_int(cell("machine_number"))
                if machine_number is None:
                    continue
                row = {
                    "machine_number": machine_number,
                    "title": cell("title") or "不明",
                    "diff_coins": _parse_int(cell("diff_coins")),
                    "rotation_count": _parse_int(cell("rotation_count")),
                    "big_count": _parse_int(cell("big_count")),
                    "reg_count": _parse_int(cell("reg_count")),
                    "final_games": _parse_int(cell("final_games")),
                }
            else:
                parsed = _infer_cols_from_row(cells)
                if not parsed.get("machine_number"):
                    continue
                row = {
                    "machine_number": parsed["machine_number"],
                    "title": parsed.get("title") or "不明",
                    "diff_coins": parsed.get("diff_coins"),
                    "rotation_count": parsed.get("rotation_count"),
                    "big_count": parsed.get("big_count"),
                    "reg_count": parsed.get("reg_count"),
                    "final_games": parsed.get("final_games"),
                }

            graph = tr.find("img")
            graph_url = graph.get("src") if graph else None
            graph_samples_json = None
            if graph_url:
                try:
                    from collector.graph_intraday import parse_graph_html, samples_to_json

                    pts = parse_graph_html(graph.get("alt", "") or "")
                    graph_samples_json = samples_to_json(pts)
                except Exception:
                    graph_samples_json = None

            rows_out.append(
                {
                    **row,
                    "captured_at": captured.isoformat(),
                    "graph_url": graph_url,
                    "graph_samples_json": graph_samples_json,
                    "is_operating": True,
                    "hist_num": hist_num,
                    "source": "daidata",
                    "store_id": store_id,
                }
            )

    return rows_out


def parse_ranking_html(html: str, store_id: str) -> list[dict[str, Any]]:
    """ランキングページからの簡易取得（補助）"""
    return parse_all_list_html(html, store_id, hist_num=0)
