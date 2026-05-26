"""機種ファミリー分類 — 機種別モデル分離の基盤"""

from typing import Literal

MachineFamily = Literal["juggler", "at", "smart_slot", "normal", "volatile", "pachinko_std"]


def classify_machine_family(title: str, game_type: str = "slot") -> MachineFamily:
    t = (title or "").strip()
    if game_type == "pachinko":
        if any(k in t for k in ("一撃", "甘", "LT", "ST")):
            return "volatile"
        return "pachinko_std"
    if "ジャグラー" in t or "Juggler" in t or "ジャグ" in t:
        return "juggler"
    if t.startswith("L") or "Ｌ" in t[:2] or "Lパチスロ" in t:
        return "at"
    if t.startswith("スマスロ") or "スマスロ" in t[:8]:
        if any(k in t for k in ("北斗", "ガンダム", "エヴァ", "モンキー", "東京リベン")):
            return "volatile"
        return "smart_slot"
    if any(k in t for k in ("押し順", "番長", "ディスク")):
        return "at"
    return "normal"


# ファミリー別スコア補正（朝スコア → リアルタイムEVへの重み）
FAMILY_EV_WEIGHTS: dict[str, dict[str, float]] = {
    "juggler": {"reg_persist": 1.2, "rotation_pace": 0.9, "one_shot": 0.7},
    "at": {"one_shot": 1.15, "waveform": 1.1, "rotation_pace": 1.0},
    "smart_slot": {"waveform": 1.2, "island_sync": 1.15, "one_shot": 1.1},
    "normal": {"rotation_pace": 1.0, "waveform": 1.0},
    "volatile": {"one_shot": 1.25, "exhaustion_penalty": 1.3},
    "pachinko_std": {"island_sync": 1.1, "rotation_pace": 0.85},
}
