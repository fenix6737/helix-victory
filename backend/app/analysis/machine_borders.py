"""
機種別等価ボーダー（1,000円あたりの合格回転数）マスタ
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 初期シード（管理画面CSVでも上書き可能）
DEFAULT_BORDERS: list[dict] = [
    {
        "title_pattern": "エヴァンゲリオン未来への咆哮",
        "border_per_1000_yen": 16.5,
        "game_type": "pachinko",
        "coin_price_yen": 4.0,
        "base_games": 400,
    },
    {
        "title_pattern": "シン・エヴァ129",
        "border_per_1000_yen": 17.1,
        "game_type": "pachinko",
        "coin_price_yen": 4.0,
        "base_games": 400,
    },
    {
        "title_pattern": "エヴァンゲリオン",
        "border_per_1000_yen": 16.8,
        "game_type": "pachinko",
        "coin_price_yen": 4.0,
        "base_games": 400,
    },
    {
        "title_pattern": "東京喰種",
        "border_per_1000_yen": 17.5,
        "game_type": "pachinko",
        "coin_price_yen": 4.0,
        "base_games": 400,
    },
    {
        "title_pattern": "ジャグラー",
        "border_per_1000_yen": 22.0,
        "game_type": "slot",
        "coin_price_yen": 20.0,
        "base_games": 250,
    },
    {
        "title_pattern": "北斗",
        "border_per_1000_yen": 21.0,
        "game_type": "slot",
        "coin_price_yen": 20.0,
        "base_games": 250,
    },
]


@dataclass
class BorderSpec:
    title_pattern: str
    border_per_1000_yen: float
    game_type: str
    coin_price_yen: float
    base_games: int


def normalize_title(title: str) -> str:
    t = (title or "").strip().upper()
    t = re.sub(r"\s+", "", t)
    return t


def match_border(title: str, rows: list[BorderSpec]) -> BorderSpec | None:
    norm = normalize_title(title)
    if not norm:
        return None
    best: BorderSpec | None = None
    best_len = 0
    for row in rows:
        pat = normalize_title(row.title_pattern)
        if pat and pat in norm and len(pat) > best_len:
            best = row
            best_len = len(pat)
    return best


def estimate_rotation_per_1000_yen(
    total_rotation: float | None,
    final_games: float | None,
    border: BorderSpec,
    diff_trend: float,
) -> tuple[float | None, float | None]:
    """
    推定回転率（回/k）と推定投資額（円）を返す。
    投資 ≈ (総回転 ÷ ベースG) × 玉価 × (250/base_games proxy)
    """
    if total_rotation is None or total_rotation <= 0:
        return None, None
    base_g = border.base_games or 250
    games = final_games if final_games and final_games > 0 else base_g
    # 1,000円あたり回転: 総回転 / (推定投資/1000)
    invest = (total_rotation / max(games, 1)) * border.coin_price_yen * (base_g / 250)
    if diff_trend < 0 and invest > 0:
        invest = max(invest, abs(diff_trend) * 0.85)
    rot_per_k = total_rotation / max(invest / 1000.0, 0.5)
    return rot_per_k, invest


def border_exceed_score(
    rot_per_k: float | None,
    border_per_k: float,
    *,
    margin: float = 1.0,
) -> tuple[float, bool]:
    """+margin 回転以上超えで最上位ソート用フラグ"""
    if rot_per_k is None:
        return 0.0, False
    exceed = rot_per_k - border_per_k
    if exceed >= margin:
        return min(1.0, 0.5 + exceed / 8.0), True
    if exceed >= 0:
        return 0.35 + exceed / margin * 0.2, False
    return max(0.0, 0.2 + exceed / 10.0), False
