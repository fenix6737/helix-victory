"""
店舗フロア配置 — 台番号から角台・角2を判定（末尾ヒューリスティックの補正）

キコーナ尼崎: 手前島の角付近（L東京喰種 33番付近など）を明示登録。
"""

from __future__ import annotations

# キコーナ尼崎本店 — ユーザー確認・フロア配置に基く角台（随時拡張可）
KICONA_AMAGASAKI_POSITIONS: dict[int, str] = {
    # 手前 L東京喰種ブロック（低番台フロント）
    31: "corner2",
    32: "corner",
    33: "corner",  # 手前の角 — 喰種33
    34: "corner",
    39: "corner2",
    # 各百番台ブロックの角（末尾1,2=角2 / 0,9=角）
    101: "corner2",
    102: "corner2",
    109: "corner",
    110: "corner",
    201: "corner2",
    202: "corner2",
    209: "corner",
    210: "corner",
    301: "corner2",
    302: "corner2",
    309: "corner",
    310: "corner",
    401: "corner2",
    402: "corner2",
    409: "corner",
    410: "corner",
    501: "corner2",
    502: "corner2",
    509: "corner",
    510: "corner",
}

_STORE_MAP: dict[str, dict[int, str]] = {
    "kicona_amagasaki": KICONA_AMAGASAKI_POSITIONS,
}


def get_machine_position(store_id: str, machine_number: int) -> str | None:
    table = _STORE_MAP.get(store_id)
    if not table:
        return None
    return table.get(machine_number)


def infer_position_with_store(
    machine_number: int,
    island_id: str | None,
    store_id: str | None,
) -> str:
    """engine.infer_position の店舗レイアウト対応版"""
    if store_id:
        custom = get_machine_position(store_id, machine_number)
        if custom:
            return custom
    tail = machine_number % 10
    if tail in (1, 2):
        return "corner2"
    if tail in (0, 9):
        return "corner"
    if tail in (5, 6):
        return "main_aisle"
    return "row"
