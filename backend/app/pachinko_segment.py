"""
パチンコ台の分析対象判定 — 4パチ・ミドルタイプ以上のみ集計・推奨対象とする。

1パチ / 2パチ / 甘デジ / ライトミドル未満などは対象外。
"""

from __future__ import annotations

import re

from app.game_type import classify_game_type

# レートがミドル未満・1パチ帯
_LOW_RATE_MARKERS = (
    "1パチ",
    "１パチ",
    "1円",
    "１円",
    "2パチ",
    "２パチ",
    "2円",
    "２円",
    "0.5円",
    "0.2円",
    "1.25",
    "1.3円",
    "羽根物",
    "羽根",
    "甘デジ",
    "ライトミドル",
    "ライト",
    "デジ小",
    "セブン機",
    "ハイブリッド",
    "1/2",
    "1/319",
)

# 4パチ・ミドル以上の明示
_MIDDLE_PLUS_MARKERS = (
    "4パチ",
    "４パチ",
    "4円",
    "４円",
    "ミドル",
    "大海",
    "海物語",
    "ライトミドル以上",
)

# 店舗実態: 4円ミドル看板（タイトルにレート表記が無い場合）
_KNOWN_4PACHI_MIDDLE_PATTERNS = (
    "エヴァンゲリオン",
    "エヴァ",
    "シン・エヴァ",
    "東京喰種",
    "喰種",
    "牙狼",
    "ガンダム",
    "からくりサーカス",
    "新世紀エヴァ",
    "バイオハザード",
    "ルパン",
    "花の慶次",
    "北斗",
    "ヱヴァ",
    "ぱちんこ エヴァ",
)


def _norm(title: str) -> str:
    t = (title or "").strip()
    t = re.sub(r"\s+", "", t)
    return t.upper()


def _is_pachinko_title(title: str) -> bool:
    if classify_game_type(title) == "pachinko":
        return True
    raw = (title or "").strip()
    pachi_hints = (
        "パチ",
        "ミドル",
        "海物語",
        "甘デジ",
        "1パチ",
        "1円",
        "2パチ",
        "4パチ",
        "羽根",
    )
    if any(h in raw for h in pachi_hints):
        return True
    if re.match(r"^e[\s\u3000]", raw, re.IGNORECASE):
        return True
    if raw.upper().startswith("CR"):
        return True
    if raw.startswith("P") and len(raw) > 1 and raw[1] not in "パ":
        return True
    return False


def pachinko_analysis_eligible(title: str) -> bool:
    """
    パチンコ台が分析・集計・推奨の対象か。
    スロットは常に True（別途 game_type で分岐）。
    """
    if not _is_pachinko_title(title):
        return True

    norm = _norm(title)
    if not norm:
        return False

    for m in _LOW_RATE_MARKERS:
        if m.upper() in norm or m in (title or ""):
            return False

    for m in _MIDDLE_PLUS_MARKERS:
        if m.upper() in norm or m in (title or ""):
            return True

    for pat in _KNOWN_4PACHI_MIDDLE_PATTERNS:
        if pat.upper() in norm:
            return True

    return False


def pachinko_segment_label(title: str) -> str:
    if not pachinko_analysis_eligible(title):
        return "low_rate_excluded"
    return "4pachi_middle_plus"
