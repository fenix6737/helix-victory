"""推奨スコア / 撤退スコア 分離 — 当たり推定と負け筋排除の両立"""

from __future__ import annotations


def compute_dual_scores(
    *,
    morning_score: float,
    current_ev: float,
    exhaustion_rate: float,
    waveform_ml_class: str,
    island_state: str,
    seat_status: str,
    island_ops_rate: float,
    drift_score: float = 0.0,
    collapse_probability: float = 0.0,
) -> dict:
    """
    recommend_score: 当たり台推定（高いほど打つ価値）
    retreat_score: 負け筋リスク（高いほど撤退）
    """
    recommend = float(current_ev)
    retreat = 0.0

    if waveform_ml_class in ("fake_release", "trap_wave", "death_wave", "death", "early_peak"):
        recommend -= 22
        retreat += 35
    elif waveform_ml_class in ("stable_setting", "right_shoulder", "late_release", "release"):
        recommend += 8
        retreat -= 5

    if island_state in ("heating", "active"):
        recommend += 6
    elif island_state in ("collapse", "dead", "exhausted"):
        recommend -= 15
        retreat += 28

    if seat_status == "free":
        recommend += 5
    elif seat_status == "watched":
        recommend -= 8
        retreat += 22
    elif seat_status == "explosive":
        recommend -= 12
        retreat += 18

    if exhaustion_rate > 0.65:
        recommend -= exhaustion_rate * 25
        retreat += exhaustion_rate * 40

    if island_ops_rate > 0.6:
        recommend += 5
    elif island_ops_rate < 0.2:
        retreat += 20

    retreat += drift_score * 25
    retreat += collapse_probability * 40
    retreat += max(0, morning_score - current_ev) * 0.5

    recommend = max(0.0, min(100.0, recommend))
    retreat = max(0.0, min(100.0, retreat))

    return {
        "recommend_score": round(recommend, 1),
        "retreat_score": round(retreat, 1),
        "hit_confidence": round(max(0, recommend - retreat * 0.35), 1),
    }
