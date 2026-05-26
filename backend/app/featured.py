"""注目機種 — 東京喰種・エヴァンゲリオン（開発者指示書 4）"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeaturedGroup:
    id: str
    label: str
    badge: str
    patterns: tuple[str, ...]


FEATURED_GROUPS: tuple[FeaturedGroup, ...] = (
    FeaturedGroup(
        id="tokyo_ghoul",
        label="東京喰種シリーズ",
        badge="喰種",
        patterns=("東京喰種", "トーキョーグール", "喰種", "TOKYO GHOUL"),
    ),
    FeaturedGroup(
        id="evangelion",
        label="エヴァンゲリオン",
        badge="エヴァ",
        patterns=(
            "エヴァンゲリオン",
            "エヴァ",
            "EVANGELION",
            "新世紀エヴァ",
            "ヱヴァ",
        ),
    ),
)


def classify_featured(title: str) -> tuple[bool, str | None, str | None]:
    """returns: is_featured, group_id, badge"""
    t = (title or "").strip()
    if not t:
        return False, None, None
    upper = t.upper()
    for g in FEATURED_GROUPS:
        for p in g.patterns:
            if p.upper() in upper or p in t:
                return True, g.id, g.badge
    return False, None, None
