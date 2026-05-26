"""ホールナビ HTML パーサー — 店舗情報"""

import re
from typing import Any

from bs4 import BeautifulSoup


def parse_hall_info(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    info: dict[str, Any] = {
        "hall_name": None,
        "address": None,
        "tel": None,
        "pachinko_count": None,
        "slot_count": None,
        "url": None,
    }

    title = soup.find("title")
    if title:
        info["hall_name"] = title.get_text(strip=True).split("|")[0].strip()

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        info["hall_name"] = h1.get_text(strip=True)

    text = soup.get_text("\n", strip=True)
    m_addr = re.search(r"(兵庫県|大阪府|京都府|[^\n]{2,40}市[^\n]{2,60})", text)
    if m_addr:
        info["address"] = m_addr.group(0)[:120]

    m_tel = re.search(r"(0\d{1,4}-\d{1,4}-\d{4})", text)
    if m_tel:
        info["tel"] = m_tel.group(1)

    m_p = re.search(r"パチンコ\s*(\d+)\s*台", text)
    m_s = re.search(r"パチスロ|スロット\s*(\d+)\s*台", text)
    if m_p and m_p.group(1):
        info["pachinko_count"] = int(m_p.group(1))
    if m_s and m_s.group(1):
        info["slot_count"] = int(m_s.group(1))

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "hall-navi.com" in href and "hole" in href:
            info["url"] = href if href.startswith("http") else f"https://hall-navi.com{href}"
            break

    return info
