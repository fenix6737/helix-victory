"""
ボーダー・回転率ベースの期待値補正（信頼性極大化 §②）
差枚だけでなく回転数・BB/RB から「打てば期待値が上がる台」を推定する。
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from app.featured import classify_featured

# スロット: 250G あたりの回転数が高いほど設定が高い想定（店舗・機種で調整可能）
SLOT_ROT_PER_250_TARGET = 28.0
SLOT_BORDER_MIN = 24.0
PACHI_BB_PER_1000G_TARGET = 4.5


def tail_digit_strength(machine_number: int, weekday: int) -> float:
    """末尾番号・曜日の簡易強さ（0〜1）— ホールクセの代理指標"""
    tail = machine_number % 10
    hot_tails = {1, 3, 5, 7, 9}
    score = 0.35 if tail in hot_tails else 0.1
    if weekday in (2, 5):  # 水・土
        score += 0.15
    return min(1.0, score)


def estimate_rotation_per_250(g: pd.DataFrame) -> float | None:
    """250枚/G あたり回転の推定（rotation_count または final_games から）"""
    rot = g["rotation_count"].dropna() if "rotation_count" in g.columns else pd.Series(dtype=float)
    if rot.notna().any() and rot.mean() > 0:
        # rotation_count が「総回転」想定
        fg = g["final_games"].dropna()
        if fg.notna().any() and fg.mean() > 0:
            return float(rot.mean() / max(fg.mean(), 1) * 250)
        return float(rot.mean() / 250)

    fg = g["final_games"].dropna()
    if fg.notna().any() and fg.mean() >= 100:
        # G数のみ: 粗い代理（低G=高回転の逆は取れないが傾向用）
        return float(25000 / max(fg.mean(), 100))
    return None


def estimate_pachinko_hit_density(g: pd.DataFrame) -> float | None:
    """パチンコ: BB+RB 合計 / 1000G 相当"""
    bb = g["big_count"].dropna() if "big_count" in g.columns else pd.Series(dtype=float)
    rb = g["reg_count"].dropna() if "reg_count" in g.columns else pd.Series(dtype=float)
    fg = g["final_games"].dropna() if "final_games" in g.columns else pd.Series(dtype=float)
    if not bb.notna().any() and not rb.notna().any():
        return None
    hits = float((bb.fillna(0) + rb.fillna(0)).mean())
    games = float(fg.mean()) if fg.notna().any() and fg.mean() > 0 else 1000.0
    return hits / max(games / 1000, 0.1)


def inverse_invest_score(g: pd.DataFrame, target_date: date) -> float:
    """
    差枚推移から投資の逆算（粗い）— ボーダー超えで出ているほど高スコア。
    前日比で差枚が改善しつつ回転が取れている台を評価。
    """
    daily = (
        g.groupby(g["captured_at"].dt.date)["diff_coins"]
        .last()
        .dropna()
        .sort_index()
    )
    if len(daily) < 2:
        return 0.0
    recent = daily.iloc[-3:]
    trend = float(recent.iloc[-1] - recent.iloc[0])
    # マイナスからプラス方向、またはプラス維持
    if trend > 500:
        return 0.9
    if trend > 0:
        return 0.55
    if trend > -800:
        return 0.25
    return 0.0


def border_ev_score(
    g: pd.DataFrame,
    machine_number: int,
    title: str,
    game_type: str,
    target_date: date,
    store_metadata: dict | None,
) -> tuple[float, list[str]]:
    """
    0〜1 の期待値スコアと理由タグ。
    """
    reasons: list[str] = []
    meta = store_metadata or {}
    score = 0.0

    rot250 = estimate_rotation_per_250(g)
    if game_type == "slot" and rot250 is not None:
        if rot250 >= SLOT_BORDER_MIN:
            ratio = min(1.0, rot250 / SLOT_ROT_PER_250_TARGET)
            score += 0.45 * ratio
            reasons.append(f"・推定回転{rot250:.0f}/250G（ボーダー超え）")
        elif rot250 >= SLOT_BORDER_MIN - 3:
            score += 0.2
            reasons.append("・回転率やや高め")

    if game_type == "pachinko":
        hd = estimate_pachinko_hit_density(g)
        if hd is not None:
            ratio = min(1.0, hd / PACHI_BB_PER_1000G_TARGET)
            score += 0.4 * ratio
            reasons.append(f"・大当たり密度{hd:.2f}/1000G")

    score += 0.25 * inverse_invest_score(g, target_date)
    score += 0.2 * tail_digit_strength(machine_number, target_date.weekday())

    feat, gid, _ = classify_featured(title)
    if feat:
        score += 0.15
        reasons.append("・看板機種（注目枠）")

    event_days = meta.get("event_days") or [3, 9]
    if target_date.day in event_days or (target_date.day % 10) in event_days:
        score += 0.1
        reasons.append("・イベント日末尾")

    return min(1.0, score), reasons
