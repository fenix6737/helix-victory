"""台タイトルからパチンコ / スロットを判定"""

import re
from typing import Literal

GameType = Literal["slot", "pachinko"]

_PACHINKO_E_PREFIX = re.compile(r"^e[\s\u3000]", re.IGNORECASE)


def classify_game_type(title: str) -> GameType:
    t = (title or "").strip()
    if not t:
        return "slot"
    # みんレポパチンコの機種表記（e バイオハザード6 等）
    if _PACHINKO_E_PREFIX.match(t) or t.upper().startswith("CR"):
        return "pachinko"
    # パチンコ（パチスロ・スマスロより先に誤判定しないよう順序注意）
    if "パチンコ" in t and "パチスロ" not in t and "スマスロ" not in t:
        return "pachinko"
    if t.startswith("P") and "パチンコ" in t:
        return "pachinko"
    return "slot"


def icon_variant(title: str, game_type: GameType) -> str:
    """UIアイコン種別"""
    t = (title or "").strip()
    if game_type == "pachinko":
        return "pachinko"
    if t.startswith("スマスロ") or "スマスロ" in t[:8]:
        return "smart_slot"
    if t.startswith("L") or "Ｌ" in t[:2] or "Lパチスロ" in t:
        return "l_slot"
    if "ジャグラー" in t or "Juggler" in t:
        return "juggler"
    if "北斗" in t or "ガンダム" in t or "エヴァ" in t:
        return "anime"
    return "slot"
