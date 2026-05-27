"""
グラフ細部データ — 時間帯別差枚から回転率を補正
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.analysis.machine_borders import BorderSpec, estimate_rotation_per_1000_yen


def parse_graph_samples(raw: str | list | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def parse_graph_html_snippet(html: str) -> list[dict[str, Any]]:
    """script内の差枚配列や data-points 属性を抽出"""
    samples: list[dict[str, Any]] = []
    for m in re.finditer(r"data-points=['\"](\[.+?\])['\"]", html, re.DOTALL):
        try:
            pts = json.loads(m.group(1).replace("'", '"'))
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    samples.append({"t": p[0], "diff": p[1]})
                elif isinstance(p, dict):
                    samples.append(p)
        except json.JSONDecodeError:
            continue
    for m in re.finditer(r"diff(?:Coins|_coins)?\s*[:=]\s*(\[[-0-9,\s]+\])", html):
        try:
            arr = json.loads(m.group(1))
            for i, v in enumerate(arr):
                samples.append({"t": i, "diff": int(v)})
        except json.JSONDecodeError:
            continue
    return samples


def refine_rotation_from_intraday(
    samples: list[dict[str, Any]],
    total_rotation: float | None,
    final_games: float | None,
    spec: BorderSpec,
    diff_trend: float,
) -> tuple[float | None, float | None]:
    """
    グラフ点列から投資ペースを補正し、回/k を再計算。
    """
    base_rot, base_inv = estimate_rotation_per_1000_yen(
        total_rotation, final_games, spec, diff_trend
    )
    if not samples or total_rotation is None:
        return base_rot, base_inv

    diffs = [int(s.get("diff", s.get("diff_coins", 0))) for s in samples if s]
    if len(diffs) < 3:
        return base_rot, base_inv

    swing = max(diffs) - min(diffs)
    if swing <= 0:
        return base_rot, base_inv

    # 差枚振幅が大きいほど実投資が増える想定で補正
    invest_factor = 1.0 + min(0.35, swing / max(abs(diff_trend) + 500, 800))
    if base_inv and base_inv > 0:
        adj_inv = base_inv * invest_factor
        rot_per_k = total_rotation / max(adj_inv / 1000.0, 0.5)
        return rot_per_k, adj_inv
    return base_rot, base_inv
