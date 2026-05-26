"""リアルタイム期待値 v2 — 消化率・時間帯補正"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analysis.machine_family import FAMILY_EV_WEIGHTS, classify_machine_family
from app.analysis.seat_status_engine import SeatStatus
from app.analysis.time_band import current_time_band, time_band_ev_adjustment


@dataclass
class CurrentEvResult:
    machine_id: int
    morning_score: float
    current_ev: float
    exhaustion_rate: float
    ev_delta: float
    playable: bool
    reasons: list[str]
    exhaustion_detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "machine_id": self.machine_id,
            "morning_score": round(self.morning_score, 1),
            "current_ev": round(self.current_ev, 1),
            "exhaustion_rate": round(self.exhaustion_rate, 3),
            "ev_delta": round(self.ev_delta, 1),
            "playable": self.playable,
            "reasons": self.reasons,
            "exhaustion_detail": self.exhaustion_detail,
        }


def compute_exhaustion_metrics(
    current_diff: float | None,
    peak_diff: float | None,
    morning_baseline: float | None,
    rotation_velocity: float,
    island_mean_exhaustion: float = 0.0,
) -> tuple[float, dict]:
    peak_reach = 0.0
    release_end = 0.0
    setting_continue = 0.0

    if current_diff is None:
        return 0.3, {"peak_reach_rate": 0, "release_end_rate": 0, "island_exhaustion": island_mean_exhaustion}

    rate = 0.0
    if peak_diff is not None and peak_diff > 500:
        consumed = (peak_diff - current_diff) / max(peak_diff, 1)
        rate = max(rate, min(1.0, consumed))
        peak_reach = rate

    if morning_baseline is not None and current_diff > morning_baseline + 800:
        rate = max(rate, 0.75)
        setting_continue = 0.7

    if current_diff > 1500:
        rate = max(rate, 0.85)

    if rotation_velocity > 2500 and current_diff > 600:
        rate = max(rate, 0.55)

    if rotation_velocity < 200 and current_diff > 400:
        release_end = 0.6
        rate = max(rate, release_end)

    rate = max(rate, min(1.0, island_mean_exhaustion * 0.4))
    detail = {
        "peak_reach_rate": round(peak_reach, 3),
        "release_end_rate": round(release_end, 3),
        "setting_continue_rate": round(setting_continue, 3),
        "island_exhaustion": round(island_mean_exhaustion, 3),
    }
    return min(1.0, rate), detail


def compute_exhaustion_rate(
    current_diff: float | None,
    peak_diff: float | None,
    morning_baseline: float | None,
    rotation_velocity: float,
) -> float:
    rate, _ = compute_exhaustion_metrics(
        current_diff, peak_diff, morning_baseline, rotation_velocity
    )
    return rate


def compute_current_ev(
    *,
    machine_id: int,
    morning_score: float,
    title: str,
    game_type: str,
    current_diff: int | None,
    peak_diff: int | None,
    rotation_velocity: float,
    island_ops_rate: float,
    waveform_ml_class: str,
    seat_status: SeatStatus,
    morning_baseline_diff: float | None = None,
    store_mode: str | None = None,
    island_state: str = "neutral",
) -> CurrentEvResult:
    family = classify_machine_family(title, game_type)
    weights = FAMILY_EV_WEIGHTS.get(family, FAMILY_EV_WEIGHTS["normal"])

    island_ex = 0.0
    if island_state in ("exhausted", "dead"):
        island_ex = 0.85
    elif island_state == "recovery":
        island_ex = 0.3

    exhaustion, ex_detail = compute_exhaustion_metrics(
        float(current_diff) if current_diff is not None else None,
        float(peak_diff) if peak_diff is not None else None,
        morning_baseline_diff,
        rotation_velocity,
        island_ex,
    )

    ev = morning_score
    reasons: list[str] = []

    ev -= exhaustion * 35 * weights.get("exhaustion_penalty", 1.0)
    if exhaustion > 0.6:
        reasons.append(f"・期待値消化 {int(exhaustion * 100)}%")

    band = current_time_band()
    adj, band_reason = time_band_ev_adjustment(band, store_mode)
    ev += adj
    if band_reason:
        reasons.append(f"・{band_reason}")

    if seat_status == SeatStatus.EXPLOSIVE:
        ev -= 22
        reasons.append("・爆発済み")
    elif seat_status == SeatStatus.ROTATING:
        ev += 5 * weights.get("rotation_pace", 1.0)
        reasons.append("・高稼働継続")
    elif seat_status == SeatStatus.ABANDONED:
        ev -= 8
        reasons.append("・放置")
    elif seat_status == SeatStatus.FREE:
        ev += 4
        reasons.append("・空席")
    elif seat_status == SeatStatus.WATCHED:
        ev -= 3
        reasons.append("・監視台")

    wf = waveform_ml_class
    if wf in ("stable_setting", "right_shoulder", "release", "late_release", "setting_like"):
        ev += 7 * weights.get("waveform", 1.0)
        reasons.append("・設定型波形")
    elif wf in ("trap_wave", "death_wave", "death", "one_shot", "fake_release", "forced_recovery"):
        ev -= 14
        reasons.append("・事故/罠波形")
    elif wf == "early_peak":
        ev -= 6
        reasons.append("・早ピーク")

    if island_ops_rate > 0.65:
        ev += 8 * weights.get("island_sync", 1.0)
        reasons.append("・島放出継続")
    elif island_ops_rate < 0.25:
        ev -= 10
        reasons.append("・島放出終了")

    if rotation_velocity > 1800 and exhaustion < 0.4:
        ev += 5
        reasons.append("・浅回転+稼働")

    if island_state == "heating":
        ev += 4
    elif island_state == "dead":
        ev -= 12

    ev = max(0.0, min(100.0, ev))
    playable = (
        ev >= 55
        and seat_status not in (SeatStatus.EXPLOSIVE,)
        and exhaustion < 0.75
        and wf not in ("trap_wave", "death_wave", "fake_release", "forced_recovery")
    )

    return CurrentEvResult(
        machine_id=machine_id,
        morning_score=morning_score,
        current_ev=ev,
        exhaustion_rate=exhaustion,
        ev_delta=ev - morning_score,
        playable=playable,
        reasons=reasons[:5],
        exhaustion_detail=ex_detail,
    )
