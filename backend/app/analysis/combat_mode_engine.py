"""実戦モード v3.5 — retreat 最上位保護"""

from __future__ import annotations

from dataclasses import dataclass

COMBAT_UI = {
    "attack": {"label": "打てる", "color": "emerald"},
    "careful": {"label": "慎重", "color": "amber"},
    "avoid": {"label": "危険", "color": "red"},
    "retreat": {"label": "撤退", "color": "slate"},
}


@dataclass
class CombatMode:
    mode: str
    label: str
    should_visit: bool
    should_play: bool
    reasons: list[str]
    ui_color: str = "emerald"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "label": self.label,
            "should_visit": self.should_visit,
            "should_play": self.should_play,
            "reasons": self.reasons,
            "ui_color": self.ui_color,
        }


def resolve_combat_mode(
    *,
    danger_level: str,
    danger_score: float,
    should_play: bool,
    integrity_ok: bool,
    anomaly_block: bool,
    manager_shift_prob: float,
    playable_count: int,
    store_mode: str | None = None,
    drift_score: float = 0.0,
    force_retreat: bool = False,
    retreat_reasons: list[str] | None = None,
) -> CombatMode:
    reasons = list(retreat_reasons or [])

    if force_retreat or not integrity_ok or anomaly_block:
        r = reasons or (
            ["撤退AI発動"] if force_retreat else ["データ異常 — 分析停止"]
            if not integrity_ok
            else ["異常検知 — 推奨停止"]
        )
        return CombatMode(
            "retreat",
            COMBAT_UI["retreat"]["label"],
            integrity_ok and not anomaly_block,
            False,
            r[:6],
            COMBAT_UI["retreat"]["color"],
        )

    if danger_level == "critical" or danger_score >= 72:
        return CombatMode(
            "retreat",
            COMBAT_UI["retreat"]["label"],
            False,
            False,
            ["critical — 強制撤退"],
            COMBAT_UI["retreat"]["color"],
        )

    if danger_level == "danger" or danger_score >= 58:
        return CombatMode(
            "avoid",
            COMBAT_UI["avoid"]["label"],
            True,
            False,
            ["危険日 — 打たない最適"],
            COMBAT_UI["avoid"]["color"],
        )

    if store_mode == "recovery" or drift_score >= 0.65:
        if drift_score >= 0.65:
            reasons.append("営業ドリフト")
        return CombatMode(
            "retreat",
            COMBAT_UI["retreat"]["label"],
            True,
            False,
            reasons or ["回収営業"],
            COMBAT_UI["retreat"]["color"],
        )

    if manager_shift_prob >= 0.5:
        return CombatMode(
            "careful",
            COMBAT_UI["careful"]["label"],
            True,
            should_play and playable_count > 0,
            ["店長変更疑い"],
            COMBAT_UI["careful"]["color"],
        )

    if danger_level == "caution" or danger_score >= 32:
        return CombatMode(
            "careful",
            COMBAT_UI["careful"]["label"],
            True,
            should_play and playable_count > 0,
            ["要注意日"],
            COMBAT_UI["careful"]["color"],
        )

    if playable_count < 3:
        return CombatMode(
            "careful",
            COMBAT_UI["careful"]["label"],
            True,
            playable_count > 0,
            ["候補不足"],
            COMBAT_UI["careful"]["color"],
        )

    if not should_play or playable_count == 0:
        return CombatMode(
            "avoid",
            COMBAT_UI["avoid"]["label"],
            True,
            False,
            ["playableなし"],
            COMBAT_UI["avoid"]["color"],
        )

    return CombatMode(
        "attack",
        COMBAT_UI["attack"]["label"],
        True,
        True,
        reasons or ["実戦"],
        COMBAT_UI["attack"]["color"],
    )
