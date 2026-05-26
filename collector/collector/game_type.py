"""収集側 — ゲーム種別判定（backend と同ロジック）"""

import re
from typing import Literal

GameType = Literal["slot", "pachinko"]

_PACHINKO_E_PREFIX = re.compile(r"^e[\s\u3000]", re.IGNORECASE)


def classify_game_type(title: str) -> GameType:
    t = (title or "").strip()
    if not t:
        return "slot"
    if _PACHINKO_E_PREFIX.match(t) or t.upper().startswith("CR"):
        return "pachinko"
    if "パチンコ" in t and "パチスロ" not in t and "スマスロ" not in t:
        return "pachinko"
    if t.startswith("P") and "パチンコ" in t:
        return "pachinko"
    return "slot"
