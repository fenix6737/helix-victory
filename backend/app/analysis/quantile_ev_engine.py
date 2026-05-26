"""Quantile EV v3.5 — 分布 + 崩壊確率"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_quantile_ev(
    g: pd.DataFrame,
    morning_score: float,
    *,
    fake_release_rate: float = 0.0,
    island_collapse_rate: float = 0.0,
    drift_score: float = 0.0,
    ops_drop_rate: float = 0.0,
) -> dict:
    diffs = g["diff_coins"].dropna().astype(float)
    if len(diffs) < 3:
        base = float(diffs.mean()) if len(diffs) else 0.0
        p25, p50, p75, p90 = base - 400, base, base + 400, base + 800
        worst = base - 800
    else:
        p25, p50, p75, p90 = np.percentile(diffs, [25, 50, 75, 90])
        worst = float(np.min(diffs))
        base = float(p50)

    dispersion = float(np.std(diffs)) if len(diffs) >= 2 else 0.0

    collapse_probability = min(
        0.95,
        fake_release_rate * 0.35
        + island_collapse_rate * 0.35
        + drift_score * 0.2
        + ops_drop_rate * 0.25,
    )

    return {
        "ev_p25": round(float(p25), 0),
        "ev_p50": round(float(p50), 0),
        "ev_p75": round(float(p75), 0),
        "ev_p90": round(float(p90), 0),
        "median_ev": round(float(p50), 0),
        "upside_ev": round(float(p90), 0),
        "downside_ev": round(float(p25), 0),
        "downside_risk": round(float(p25), 0),
        "worst_case_ev": round(float(worst), 0),
        "worst_case": round(float(worst), 0),
        "dispersion": round(dispersion, 1),
        "collapse_probability": round(collapse_probability, 3),
        "morning_score": morning_score,
    }
