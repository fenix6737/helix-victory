"""投資予測 v3.5 — death_line 連動撤退"""

from __future__ import annotations

from app.analysis.time_band import current_time_band


def predict_investment(
    *,
    title: str,
    game_type: str,
    morning_score: float,
    rotation_velocity: float = 0.0,
    waveform_ml_class: str = "",
    island_state: str = "neutral",
    seat_status: str = "occupied",
    store_mode: str | None = None,
    exhaustion_rate: float = 0.0,
    collapse_probability: float = 0.0,
    retreat_score: float = 0.0,
) -> dict:
    is_pach = game_type == "pachinko"
    # 実戦向けに控えめ（従来は過大になりやすかった）
    base = 2800.0 if is_pach else 2200.0
    base *= max(0.7, 1.15 - morning_score / 120.0)

    band = current_time_band()
    hourly_loss = 800.0 if is_pach else 600.0
    if band == "night":
        hourly_loss *= 1.2
    elif band == "morning":
        hourly_loss *= 0.9

    if rotation_velocity > 2000:
        base *= 0.85
        hourly_loss *= 1.1
    elif rotation_velocity < 400:
        base *= 1.12

    wf = waveform_ml_class or ""
    collapse_risk = collapse_probability
    if wf in ("trap_wave", "death_wave", "death", "fake_release"):
        base *= 1.22
        collapse_risk = min(0.95, collapse_risk + 0.2)
    elif wf in ("stable_setting", "right_shoulder"):
        base *= 0.88
        collapse_risk *= 0.85

    if island_state in ("collapse", "exhausted", "dead"):
        base *= 1.25
        collapse_risk = min(0.95, collapse_risk + 0.25)
    elif island_state in ("heating", "active"):
        base *= 0.9

    if seat_status == "watched":
        base *= 1.05
    elif seat_status == "explosive":
        base *= 1.28

    if store_mode == "recovery":
        base *= 1.12
        collapse_risk = min(0.95, collapse_risk + 0.1)

    base *= 1.0 + exhaustion_rate * 0.35 + retreat_score / 200.0

    expected = round(base, 0)
    max_risk = round(base * 1.65, 0)
    low_zone = round(base * 0.55, 0)
    death_line = round(base * (1.35 + collapse_risk * 0.4), 0)

    deep_hole = 0.12 + collapse_risk * 0.35
    if wf in ("trap_wave", "death_wave"):
        deep_hole += 0.2
    if exhaustion_rate > 0.5:
        deep_hole += 0.12
    deep_hole = min(0.9, round(deep_hole, 2))

    exceed_death = expected >= death_line

    dangerous_investment = round(max_risk * 0.92, 0)
    deep_harami_alert = deep_hole >= 0.45 or exceed_death

    return {
        "expected_investment": expected,
        "max_risk_line": max_risk,
        "dangerous_investment": dangerous_investment,
        "low_risk_zone": low_zone,
        "death_line": death_line,
        "collapse_risk": round(collapse_risk, 3),
        "deep_hole_probability": deep_hole,
        "deep_harami_alert": deep_harami_alert,
        "hourly_loss_rate": round(hourly_loss, 0),
        "time_band": band,
        "exceed_death_line": exceed_death,
    }
