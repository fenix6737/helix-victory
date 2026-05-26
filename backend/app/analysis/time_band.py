"""時間帯帯 — 初日から使えるルール補正（長期ログ不要）"""

from __future__ import annotations

from app.timeutil import jst_now


def current_time_band() -> str:
    """morning | midday | evening | night"""
    h = jst_now().hour
    if 6 <= h < 11:
        return "morning"
    if 11 <= h < 16:
        return "midday"
    if 16 <= h < 20:
        return "evening"
    return "night"


def time_band_ev_adjustment(band: str, store_mode: str | None = None) -> tuple[float, str | None]:
    """
    EV加減点と理由。正=加点、負=減点。
  """
    mode = store_mode or "normal"
    if band == "morning":
        if mode == "release":
            return 4.0, "朝: 放出立ち上がり"
        return 2.0, "朝: 抽選・据え監視"
    if band == "midday":
        if mode == "recovery":
            return -6.0, "昼: 中間設定放棄疑い"
        return -1.0, "昼: 島移動警戒"
    if band == "evening":
        return 5.0, "夕: 本命放出帯"
    # night
    if mode in ("recovery", "event"):
        return -8.0, "夜: 回収移行・EV低下"
    return -3.0, "夜: 回収警戒"
