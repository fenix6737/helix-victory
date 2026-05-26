"""島ライブ v2 — heating / active / exhausted / dead / recovery"""

from __future__ import annotations

import pandas as pd


def _classify_island_state(
    ops_rate: float,
    island_mean: float,
    sync: float,
    surge: bool,
    release_count: int,
) -> str:
    if ops_rate < 0.15 and island_mean < -500:
        return "dead"
    if island_mean < -350 and ops_rate < 0.3:
        return "exhausted"
    if surge and ops_rate > 0.45:
        return "heating"
    if ops_rate > 0.55 and island_mean > 150 and sync > 0.45:
        return "active"
    if ops_rate > 0.35 and abs(island_mean) < 200 and sync > 0.35:
        return "stable"
    if release_count >= 2 and island_mean > 0:
        return "recovery"
    if ops_rate > 0.4:
        return "active"
    return "recovery"


def compute_island_live(df: pd.DataFrame, window_hours: float = 8.0) -> dict[str, dict]:
    if df.empty or "island_id" not in df.columns:
        return {}

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    cutoff = df["captured_at"].max() - pd.Timedelta(hours=window_hours)
    recent = df[df["captured_at"] >= cutoff]

    out: dict[str, dict] = {}
    for island_id, g in recent.groupby("island_id"):
        if pd.isna(island_id) or not str(island_id).strip():
            continue
        iid = str(island_id)
        ops = g["is_operating"].dropna()
        ops_rate = float(ops.mean()) if len(ops) else 0.0

        diffs = g.groupby("machine_id")["diff_coins"].last().dropna()
        island_mean = float(diffs.mean()) if len(diffs) else 0.0
        sync = 0.0
        release_count = 0
        if len(diffs) >= 3:
            sync = sum(1 for v in diffs if v > 0) / len(diffs)
            release_count = sum(1 for v in diffs if v > 400)

        hourly = g.groupby(g["captured_at"].dt.hour)["diff_coins"].mean()
        surge = False
        move_rate = 0.0
        if len(hourly) >= 2:
            surge = float(hourly.iloc[-1] - hourly.iloc[0]) > 300
            move_rate = abs(float(hourly.iloc[-1] - hourly.iloc[0])) / 500.0

        empty_before = g.groupby("machine_id")["is_operating"].apply(
            lambda s: float((~s.fillna(True)).tail(3).mean()) if len(s) else 0
        )
        vacancy_drop = float(empty_before.mean()) if len(empty_before) else 0.0

        state = _classify_island_state(ops_rate, island_mean, sync, surge, release_count)
        temp = "neutral"
        if state == "heating":
            temp = "warming"
        elif state == "active":
            temp = "hot"
        elif state in ("dead", "exhausted"):
            temp = "cold"

        out[iid] = {
            "island_id": iid,
            "state": state,
            "ops_rate": round(ops_rate, 3),
            "mean_diff": round(island_mean, 1),
            "sync_rate": round(sync, 3),
            "move_rate": round(move_rate, 3),
            "surge": surge,
            "temperature": temp,
            "release_machines": release_count,
            "vacancy_drop": round(vacancy_drop, 3),
            "machine_count": int(g["machine_id"].nunique()),
        }
    return out
