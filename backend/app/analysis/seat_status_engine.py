"""空席戦略 v2 — free / occupied / rotating / abandoned / explosive / watched"""

from enum import Enum

import pandas as pd


class SeatStatus(str, Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    ROTATING = "rotating"
    ABANDONED = "abandoned"
    EXPLOSIVE = "explosive"
    WATCHED = "watched"


def infer_seat_status(g: pd.DataFrame) -> SeatStatus:
    if g.empty:
        return SeatStatus.FREE

    g = g.sort_values("captured_at")
    latest = g.iloc[-1]
    diff = latest.get("diff_coins")
    ops = latest.get("is_operating")

    recent = g.tail(8)
    rot = recent["rotation_count"].dropna()
    rot_vel = 0.0
    if len(rot) >= 2:
        rot_vel = float(rot.iloc[-1] - rot.iloc[0]) / max(len(rot) - 1, 1)

    peak = float(recent["diff_coins"].max()) if recent["diff_coins"].notna().any() else 0.0
    cur = float(diff) if pd.notna(diff) else 0.0

    if ops is False or (pd.isna(diff) and rot_vel < 50):
        return SeatStatus.FREE

    if peak > 1200 and cur < peak * 0.35:
        return SeatStatus.EXPLOSIVE

    if rot_vel > 400 or (pd.notna(ops) and ops and rot_vel > 200):
        return SeatStatus.ROTATING

    # 監視台: 稼働あるが回転浅く差枚横ばい
    if (
        pd.notna(ops)
        and ops
        and rot_vel < 80
        and abs(cur) < 350
        and len(recent) >= 4
    ):
        stable = recent["diff_coins"].dropna()
        if len(stable) >= 3 and float(stable.std()) < 120:
            return SeatStatus.WATCHED

    if rot_vel < 30 and pd.notna(diff) and abs(cur) < 200:
        return SeatStatus.ABANDONED

    return SeatStatus.OCCUPIED


def seat_status_label(status: SeatStatus) -> str:
    return {
        SeatStatus.FREE: "空席",
        SeatStatus.OCCUPIED: "稼働中",
        SeatStatus.ROTATING: "回転中",
        SeatStatus.ABANDONED: "放置",
        SeatStatus.EXPLOSIVE: "爆発済",
        SeatStatus.WATCHED: "監視",
    }.get(status, "不明")
