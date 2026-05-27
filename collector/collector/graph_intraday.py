"""グラフURL/HTMLから時間帯差枚サンプルを抽出"""

from __future__ import annotations

import json
import re
from typing import Any


def parse_graph_html(html: str) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    if not html:
        return samples
    for m in re.finditer(r"data-points=['\"](\[.+?\])['\"]", html, re.DOTALL):
        try:
            pts = json.loads(m.group(1).replace("'", '"'))
            for p in pts:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    samples.append({"t": p[0], "diff": int(p[1])})
        except json.JSONDecodeError:
            continue
    for m in re.finditer(r"(\[[-0-9,\s]{8,}\])", html):
        try:
            arr = json.loads(m.group(1))
            if isinstance(arr, list) and len(arr) >= 4 and all(isinstance(x, int) for x in arr):
                for i, v in enumerate(arr):
                    samples.append({"t": i, "diff": v})
                break
        except json.JSONDecodeError:
            continue
    return samples


def samples_to_json(samples: list[dict[str, Any]]) -> str | None:
    if not samples:
        return None
    return json.dumps(samples[:120], ensure_ascii=False)
