"""撤退AI — 第一候補停止 + 第二候補切替（最優先保護）"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TRAP_WAVES = frozenset({"fake_release", "trap_wave", "death_wave", "death", "forced_recovery"})


@dataclass
class RetreatDecision:
    should_retreat: bool
    should_play: bool
    reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    stop_primary: bool = False
    switch_alternative: bool = False

    def to_dict(self) -> dict:
        return {
            "should_retreat": self.should_retreat,
            "should_play": self.should_play,
            "retreat_reason": self.reasons,
            "retreat_tags": self.tags,
            "stop_primary": self.stop_primary,
            "switch_alternative": self.switch_alternative,
        }


def evaluate_retreat(
    *,
    primary: dict | None,
    candidates: list[dict],
    df: pd.DataFrame,
    islands: dict,
    drift: dict,
    danger_level: str,
    danger_score: float,
    island_collapsed: bool = False,
    collapse_probability: float = 0.0,
    investment: dict | None = None,
) -> RetreatDecision:
    reasons: list[str] = []
    tags: list[str] = []
    should_retreat = False

    if island_collapsed:
        should_retreat = True
        reasons.append("島崩壊検知")
        tags.append("island_collapse")

    if danger_level == "critical" or danger_score >= 72:
        should_retreat = True
        reasons.append("danger critical")
        tags.append("danger_critical")

    if float(drift.get("drift_score", 0)) >= 0.7:
        should_retreat = True
        reasons.append("drift急変")
        tags.append("drift_spike")

    if collapse_probability >= 0.55:
        should_retreat = True
        reasons.append(f"崩壊確率 {collapse_probability:.0%}")
        tags.append("collapse_prob")

    inv = investment or {}
    death_line = float(inv.get("death_line", 0))
    expected = float(inv.get("expected_investment", 0))
    if death_line > 0 and expected >= death_line:
        should_retreat = True
        reasons.append("death_line超過")
        tags.append("death_line")

    if not primary:
        return RetreatDecision(
            should_retreat=should_retreat,
            should_play=not should_retreat and bool(candidates),
            reasons=reasons,
            tags=tags,
            stop_primary=True,
            switch_alternative=bool(candidates),
        )

    wf = primary.get("waveform_ml_class", "")
    if wf in TRAP_WAVES:
        should_retreat = True
        reasons.append(f"波形: {wf}")
        tags.append(wf)

    if primary.get("seat_status") == "watched":
        should_retreat = True
        reasons.append("監視台 — 着席競争")
        tags.append("watched")

    ex = float(primary.get("exhaustion_rate", 0))
    ev_delta = float(primary.get("ev_delta", 0))
    if ex > 0.78 or ev_delta < -18:
        should_retreat = True
        reasons.append("EV急落/消化")
        tags.append("ev_drop")

    iid = str(primary.get("island_id") or "")
    isl = islands.get(iid, {})
    if isl.get("state") in ("exhausted", "dead", "collapse"):
        should_retreat = True
        reasons.append("島失速/放出終了")
        tags.append("island_slow")

    ops = float(isl.get("ops_rate", 0.5))
    if ops < 0.12:
        should_retreat = True
        reasons.append("稼働消失")
        tags.append("ops_gone")

    if iid and not df.empty:
        ig = df[df["island_id"].astype(str) == iid]
        if not ig.empty:
            recent = ig.sort_values("captured_at").tail(20)
            mean_now = float(recent["diff_coins"].dropna().tail(5).mean()) if len(recent) >= 3 else 0
            mean_old = float(recent["diff_coins"].dropna().head(5).mean()) if len(recent) >= 5 else mean_now
            if mean_now < mean_old - 400:
                should_retreat = True
                reasons.append("周辺台沈下")
                tags.append("neighbor_sink")

    mid = primary.get("machine_id")
    if mid and not df.empty:
        mg = df[df["machine_id"] == mid].sort_values("captured_at")
        if len(mg) >= 4:
            ops_s = mg["is_operating"].tail(4)
            if ops_s.notna().any() and float(ops_s.fillna(False).mean()) < 0.2:
                should_retreat = True
                reasons.append("稼働消失")
                tags.append("machine_ops")

    sync = float(isl.get("sync_rate", 0.5))
    if sync < 0.2 and ops < 0.35:
        should_retreat = True
        reasons.append("並び崩壊")
        tags.append("row_break")

    alts_available = any(
        c.get("machine_id") != primary.get("machine_id") and c.get("playable", True)
        for c in candidates
    )

    return RetreatDecision(
        should_retreat=should_retreat,
        should_play=not should_retreat and primary.get("playable", True),
        reasons=reasons[:8],
        tags=tags[:10],
        stop_primary=should_retreat,
        switch_alternative=should_retreat and alts_available,
    )


def apply_retreat_to_candidates(
    primary: dict | None,
    candidates: list[dict],
    retreat: RetreatDecision,
) -> tuple[dict | None, list[dict], dict | None]:
    """撤退時: primary を alternatives 先頭に差し替え。"""
    if not retreat.should_retreat or not retreat.switch_alternative:
        return primary, candidates, None

    alts = [c for c in candidates if c.get("machine_id") != (primary or {}).get("machine_id")]
    alts = sorted(alts, key=lambda x: float(x.get("current_ev", x.get("score", 0))), reverse=True)
    if not alts:
        return None, candidates, primary

    new_primary = alts[0]
    rest = alts[1:] + ([primary] if primary else [])
    return new_primary, rest[:2], primary
