"""第二候補 v3.5 — 着席競争・同島最優先"""

from __future__ import annotations

import pandas as pd


def find_alternatives(
    primary: dict,
    candidates: list[dict],
    df: pd.DataFrame,
    limit: int = 2,
    islands: dict | None = None,
) -> list[dict]:
    if not candidates or not primary:
        return []

    pid = primary.get("machine_id")
    pnum = primary.get("machine_number", 0)
    pisland = primary.get("island_id")
    pwf = primary.get("waveform_ml_class") or primary.get("waveform")
    ptemp = islands.get(str(pisland), {}).get("state") if pisland and islands else None

    scored: list[tuple[float, dict]] = []
    for c in candidates:
        if c.get("machine_id") == pid:
            continue
        if c.get("seat_status") == "watched":
            continue
        if c.get("waveform_ml_class") in ("fake_release", "trap_wave", "death_wave"):
            continue
        if not c.get("playable", True) and float(c.get("retreat_score", 0)) > 50:
            continue

        score = float(c.get("recommend_score", c.get("current_ev", c.get("score", 0))))
        mid = c.get("machine_id")
        island = c.get("island_id")
        num = int(c.get("machine_number") or 0)

        mrow = df[df["machine_id"] == mid] if not df.empty else pd.DataFrame()
        if not mrow.empty:
            island = island or mrow.iloc[-1].get("island_id")
            num = int(mrow.iloc[-1].get("machine_number") or num)

        same_island = pisland and island and str(island) == str(pisland)
        if same_island:
            score += 30
            c["island_id"] = str(island)
        else:
            if pisland and island:
                score -= 45
            if abs(num - pnum) > 15:
                score -= 30

        if abs(num - pnum) <= 2:
            score += 15
        elif abs(num - pnum) <= 6:
            score += 8

        if islands and island and ptemp:
            ist = islands.get(str(island), {})
            if ist.get("state") == ptemp:
                score += 10
            if ist.get("sync_rate", 0) > 0.5 and same_island:
                score += 8

        if c.get("waveform_ml_class") == pwf:
            score += 7

        if c.get("seat_status") == "free":
            score += 6

        if score < 25:
            continue
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    alts: list[dict] = []
    for i, (_, c) in enumerate(scored[:limit], start=2):
        alts.append(
            {
                "rank": i,
                "machine_id": c.get("machine_id"),
                "machine_number": c.get("machine_number"),
                "title": c.get("title"),
                "current_ev": c.get("current_ev"),
                "recommend_score": c.get("recommend_score"),
                "seat_status": c.get("seat_status"),
                "island_id": c.get("island_id"),
                "reason": _alt_reason(primary, c),
            }
        )
    return alts


def _alt_reason(primary: dict, alt: dict) -> str:
    if primary.get("island_id") and alt.get("island_id") == primary.get("island_id"):
        return "同島・同期"
    if abs(int(alt.get("machine_number", 0)) - int(primary.get("machine_number", 0))) <= 3:
        return "同列近傍"
    if alt.get("waveform_ml_class") == primary.get("waveform_ml_class"):
        return "波形近似"
    if alt.get("seat_status") == "free":
        return "空席"
    return "次点"
