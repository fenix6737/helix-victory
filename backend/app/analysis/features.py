"""特徴量生成 — 挙動分析の核（島投入・特定日・波形）"""

from datetime import date, timedelta

import numpy as np
import pandas as pd


def _daily_last(g: pd.DataFrame, col: str) -> pd.Series:
    return g.groupby(g["captured_at"].dt.date)[col].last()


def _waveform_scores(g: pd.DataFrame) -> dict[str, float]:
    """差枚の日内・日次波形パターン"""
    if g["diff_coins"].notna().sum() < 4:
        return {
            "wave_morning_rise": 0.0,
            "wave_one_shot": 0.0,
            "wave_evening_spike": 0.0,
            "wave_abnormal_ops": 0.0,
            "wave_ops_sudden": 0.0,
        }

    g = g.dropna(subset=["diff_coins"]).copy()
    g["hour"] = g["captured_at"].dt.hour

    # 朝→右肩: 10-12時平均 < 18-21時平均
    morning = g[g["hour"].between(10, 12)]["diff_coins"].mean()
    evening = g[g["hour"].between(18, 21)]["diff_coins"].mean()
    wave_morning_rise = 1.0 if (
        pd.notna(morning) and pd.notna(evening) and evening > morning + 300
    ) else 0.0

    # 一撃型: 直近で1回だけ大きな上げ
    diffs = g["diff_coins"].diff().dropna()
    wave_one_shot = 1.0 if (diffs.max() >= 1500 and (diffs >= 1000).sum() <= 2) else 0.0

    # 夕方急伸
    wave_evening_spike = 1.0 if (
        pd.notna(evening) and pd.notna(morning) and evening - morning >= 800
    ) else 0.0

    # 異常稼働 / 稼働急変
    rot = g["rotation_count"].dropna()
    wave_abnormal_ops = 0.0
    wave_ops_sudden = 0.0
    if len(rot) >= 3:
        rot_mean = rot.mean()
        rot_std = rot.std()
        if rot_std > 0 and (rot.max() > rot_mean + 2.5 * rot_std):
            wave_abnormal_ops = 1.0
        rot_diff = rot.diff().dropna()
        if len(rot_diff) and rot_diff.abs().max() >= rot_mean * 0.5:
            wave_ops_sudden = 1.0

    return {
        "wave_morning_rise": wave_morning_rise,
        "wave_one_shot": wave_one_shot,
        "wave_evening_spike": wave_evening_spike,
        "wave_abnormal_ops": wave_abnormal_ops,
        "wave_ops_sudden": wave_ops_sudden,
    }


def _island_injection_score(df: pd.DataFrame, island_id: str | None, target_date: date) -> float:
    if not island_id or island_id not in df["island_id"].values:
        return 0.0
    island_df = df[df["island_id"] == island_id]
    recent = island_df[island_df["captured_at"].dt.date >= target_date - timedelta(days=3)]
    if recent.empty:
        return 0.0
    daily_mean = recent.groupby(recent["captured_at"].dt.date)["diff_coins"].mean()
    if len(daily_mean) < 2:
        return 0.0
    if daily_mean.iloc[-1] > daily_mean.iloc[:-1].mean() + 200:
        return 1.0
    return 0.0


def _specific_day_score(g: pd.DataFrame, target_date: date) -> float:
    """同曜日・同月日の過去実績"""
    target_weekday = target_date.weekday()
    target_dom = target_date.day
    hist = g[g["captured_at"].dt.date < target_date]
    if hist.empty:
        return 0.0

    wd = hist[hist["captured_at"].dt.weekday == target_weekday]
    dom = hist[hist["captured_at"].dt.day == target_dom]

    scores = []
    for subset in (wd, dom):
        if len(subset) >= 3:
            daily = subset.groupby(subset["captured_at"].dt.date)["diff_coins"].last().mean()
            if pd.notna(daily) and daily > 0:
                scores.append(1.0)
    return 1.0 if scores else 0.0


def _recover_then_inject(g: pd.DataFrame) -> float:
    daily = _daily_last(g, "diff_coins").dropna()
    if len(daily) < 4:
        return 0.0
    vals = daily.tolist()
    for i in range(2, len(vals)):
        if vals[i - 2] < -500 and vals[i - 1] < 0 and vals[i] > 500:
            return 1.0
    return 0.0


def build_features(df: pd.DataFrame, target_date: date) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    df = df.sort_values(["machine_id", "captured_at"])

    # 島単位の当日平均（投入傾向）
    island_stats: dict[str, float] = {}
    recent_all = df[df["captured_at"].dt.date >= target_date - timedelta(days=1)]
    if not recent_all.empty and recent_all["island_id"].notna().any():
        for iid, ig in recent_all.groupby("island_id"):
            if pd.notna(iid):
                island_stats[str(iid)] = float(ig["diff_coins"].dropna().mean() or 0)

    rows = []
    for machine_id, g in df.groupby("machine_id"):
        g = g.sort_values("captured_at")
        latest = g.iloc[-1]

        daily = _daily_last(g, "diff_coins").dropna()
        sunk_days = 0
        for v in reversed(daily.tolist()):
            if v < 0:
                sunk_days += 1
            else:
                break

        recent = g[g["captured_at"] >= pd.Timestamp(target_date - timedelta(days=7), tz="UTC")]
        diff_range = 0.0
        if len(recent) >= 2 and recent["diff_coins"].notna().sum() >= 2:
            diffs = recent["diff_coins"].dropna()
            diff_range = float(diffs.max() - diffs.min())

        rot_mean = float(g["rotation_count"].dropna().mean()) if g["rotation_count"].notna().any() else 0.0
        missing_rate = float(g[["diff_coins", "rotation_count"]].isna().mean().mean())

        pos = latest.get("position_type") or "unknown"
        is_corner = 1 if pos in ("corner", "corner2") else 0
        is_corner2 = 1 if pos == "corner2" else 0

        island_id = latest.get("island_id")
        island_str = str(island_id) if pd.notna(island_id) else None
        island_boost = _island_injection_score(df, island_str, target_date)
        specific_day = _specific_day_score(g, target_date)
        recover_inject = _recover_then_inject(g)
        waves = _waveform_scores(g)

        rows.append(
            {
                "machine_id": machine_id,
                "sunk_days": sunk_days,
                "diff_range_7d": diff_range,
                "hold_score": 1.0 if diff_range <= 500 else 0.0,
                "rot_mean": rot_mean,
                "missing_rate": missing_rate,
                "is_corner": is_corner,
                "is_corner2": is_corner2,
                "weekday_match": specific_day,
                "specific_day_score": specific_day,
                "island_boost": island_boost,
                "recover_inject": recover_inject,
                "latest_diff": float(latest["diff_coins"]) if pd.notna(latest["diff_coins"]) else 0.0,
                "sample_count": len(g),
                **waves,
            }
        )

    return pd.DataFrame(rows)
