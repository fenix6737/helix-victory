"""島崩壊検知 — collapse 時は retreat 最優先"""

from __future__ import annotations

import pandas as pd


def detect_island_collapse(
    islands: dict[str, dict],
    df: pd.DataFrame,
    window_hours: float = 4.0,
) -> dict:
    """
    島ごとに崩壊判定。返却: collapsed_islands, any_collapse, primary_island_collapsed
    """
    collapsed: list[str] = []
    signals: dict[str, list[str]] = {}

    if df.empty or not islands:
        return {
            "any_collapse": False,
            "collapsed_islands": [],
            "island_signals": signals,
            "collapse_rate": 0.0,
        }

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    cutoff = df["captured_at"].max() - pd.Timedelta(hours=window_hours)
    recent = df[df["captured_at"] >= cutoff]

    for iid, meta in islands.items():
        if not iid:
            continue
        sigs: list[str] = []
        ig = recent[recent["island_id"].astype(str) == str(iid)]
        if ig.empty:
            continue

        ops = float(meta.get("ops_rate", 0))
        if ops < 0.1:
            sigs.append("rotation_stop")
        if meta.get("state") in ("dead", "exhausted"):
            sigs.append("temp_drop")

        hourly = ig.groupby(ig["captured_at"].dt.hour)["diff_coins"].mean()
        if len(hourly) >= 2 and float(hourly.iloc[-1] - hourly.iloc[0]) < -350:
            sigs.append("temp_crash")

        sync = float(meta.get("sync_rate", 0))
        if sync < 0.15:
            sigs.append("row_break")

        rel = int(meta.get("release_machines", 0))
        if rel == 0 and ops < 0.25:
            sigs.append("release_stop")

        if float(meta.get("vacancy_drop", 0)) > 0.5:
            sigs.append("vacancy_surge")

        death_waves = 0
        for mid in ig["machine_id"].unique():
            mg = ig[ig["machine_id"] == mid].sort_values("captured_at")
            diffs = mg["diff_coins"].dropna().astype(float)
            if len(diffs) >= 3:
                deltas = diffs.diff().dropna()
                if len(deltas) and float((deltas < -400).mean()) > 0.4:
                    death_waves += 1
        if death_waves >= 2:
            sigs.append("death_wave_cluster")

        if len(sigs) >= 2:
            collapsed.append(str(iid))
            signals[str(iid)] = sigs
            meta["state"] = "collapse"

    rate = len(collapsed) / max(len(islands), 1)
    return {
        "any_collapse": len(collapsed) > 0,
        "collapsed_islands": collapsed,
        "island_signals": signals,
        "collapse_rate": round(rate, 3),
    }


def primary_island_collapsed(primary: dict | None, collapse_info: dict) -> bool:
    if not primary:
        return collapse_info.get("any_collapse", False)
    iid = str(primary.get("island_id") or "")
    return iid in collapse_info.get("collapsed_islands", [])
