"""
店舗特化型 高期待値抽出エンジン — 多層分析 + 除外 + 3区分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum

import numpy as np
import pandas as pd

from app.analysis.border_ev import border_ev_score
from app.analysis.machine_borders import BorderSpec
from app.analysis.island import compute_island_stats, enrich_island_column
from app.config import settings
from app.game_type import classify_game_type


class StoreMode(str, Enum):
    RECOVERY = "recovery"
    NORMAL = "normal"
    RELEASE = "release"
    EVENT = "event"


class WaveformType(str, Enum):
    RIGHT_SHOULDER = "right_shoulder"
    V_SHAPE = "v_shape"
    ONE_SHOT = "one_shot"
    DEATH = "death"
    RELEASE = "release"
    UNKNOWN = "unknown"


class VerdictTier(str, Enum):
    RECOMMEND = "recommend"
    HOLD = "hold"
    EXCLUDE = "exclude"


@dataclass
class LayerWeights:
    """自動再調整対象の重み"""
    specific_day: float = 1.0
    position: float = 1.0
    waveform: float = 1.0
    island: float = 1.0
    time_slot: float = 1.0
    exclusion_penalty: float = 1.0
    border_ev: float = 1.0
    tail_digit: float = 1.0

    @classmethod
    def from_dict(cls, d: dict | None) -> LayerWeights:
        if not d:
            return cls()
        return cls(
            specific_day=float(d.get("specific_day", 1.0)),
            position=float(d.get("position", 1.0)),
            waveform=float(d.get("waveform", 1.0)),
            island=float(d.get("island", 1.0)),
            time_slot=float(d.get("time_slot", 1.0)),
            exclusion_penalty=float(d.get("exclusion_penalty", 1.0)),
            border_ev=float(d.get("border_ev", 1.0)),
            tail_digit=float(d.get("tail_digit", 1.0)),
        )

    def to_dict(self) -> dict:
        return {
            "specific_day": self.specific_day,
            "position": self.position,
            "waveform": self.waveform,
            "island": self.island,
            "time_slot": self.time_slot,
            "exclusion_penalty": self.exclusion_penalty,
            "border_ev": self.border_ev,
            "tail_digit": self.tail_digit,
        }


def detect_store_mode(
    df: pd.DataFrame,
    target_date: date,
    event_days: list[int] | None = None,
) -> StoreMode:
    recent = df[pd.to_datetime(df["captured_at"]).dt.date >= target_date - timedelta(days=5)]
    if recent.empty:
        return StoreMode.NORMAL
    daily = recent.groupby(pd.to_datetime(recent["captured_at"]).dt.date)["diff_coins"].mean()
    if len(daily) < 2:
        return StoreMode.NORMAL
    trend = daily.iloc[-1] - daily.iloc[0]
    ev_days = event_days or [3, 9]
    if target_date.day in ev_days or (target_date.day % 10) in ev_days:
        return StoreMode.EVENT
    if trend < -300:
        return StoreMode.RECOVERY
    if trend > 300:
        return StoreMode.RELEASE
    return StoreMode.NORMAL


def classify_waveform(g: pd.DataFrame) -> WaveformType:
    diffs = g["diff_coins"].dropna()
    if len(diffs) < 4:
        return WaveformType.UNKNOWN
    vals = diffs.values
    if vals[-1] < -1500 and vals.max() < 0:
        return WaveformType.DEATH
    if vals[-1] > 800 and vals[0] < vals[-1] - 500:
        return WaveformType.RIGHT_SHOULDER
    if vals.min() < -800 and vals[-1] > 500:
        return WaveformType.V_SHAPE
    if np.max(np.diff(vals)) >= 1500 and (vals >= 1000).sum() <= 2:
        return WaveformType.ONE_SHOT
    if vals[-1] > 600:
        return WaveformType.RELEASE
    return WaveformType.UNKNOWN


def infer_position(machine_number: int, island_id: str | None) -> str:
    tail = machine_number % 10
    if tail in (1, 2):
        return "corner2"
    if tail in (0, 9):
        return "corner"
    if tail in (5, 6):
        return "main_aisle"
    return "row"


def _time_slot_features(g: pd.DataFrame) -> dict[str, float]:
    g = g.copy()
    g["hour"] = pd.to_datetime(g["captured_at"]).dt.hour
    morning = g[g["hour"].between(10, 11)]["rotation_count"].mean()
    afternoon = g[g["hour"].between(14, 16)]["rotation_count"].mean()
    evening = g[g["hour"].between(18, 21)]["diff_coins"].mean()
    open_rot = float(morning) if pd.notna(morning) else 0.0
    afternoon_growth = (
        float(afternoon - morning) if pd.notna(afternoon) and pd.notna(morning) else 0.0
    )
    evening_spike = float(evening) if pd.notna(evening) else 0.0
    return {
        "open_hour_rot": open_rot,
        "afternoon_growth": afternoon_growth,
        "evening_spike": evening_spike,
    }


def _store_min_samples(store_id: str, df: pd.DataFrame, game_type: str) -> int:
    """収集日数が少ない店舗でも推奨を出せるよう、実データに合わせて下限を調整"""
    base = 15 if game_type == "pachinko" else settings.analysis_min_samples
    if df.empty or "machine_id" not in df.columns:
        return base
    gdf = df
    if game_type in ("slot", "pachinko") and "game_type" in df.columns:
        gdf = df[df["game_type"] == game_type]
        if gdf.empty:
            return base
    counts = gdf.groupby("machine_id").size()
    if counts.empty:
        return base
    typical = int(counts.median())
    if typical >= base:
        return base
    # 短期収集店舗: 中央値に合わせて下限（マルハンは7日分など）
    floor = 5 if store_id == "maruhan_umeda" else 8
    return max(floor, min(base, typical))


def _exclusion_checks(
    row: dict,
    store_mode: StoreMode,
    island_row: dict | None,
    game_type: str = "slot",
    *,
    min_samples: int | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    exclude = False
    min_samples = min_samples or (15 if game_type == "pachinko" else settings.analysis_min_samples)
    min_ops = 0.12 if game_type == "pachinko" else 0.25
    miss_max = 0.35 if game_type == "pachinko" else settings.analysis_missing_rate_max

    if row.get("sample_count", 0) < min_samples:
        reasons.append("・サンプル不足")
        exclude = True
    if row.get("missing_rate", 0) > miss_max:
        reasons.append("・データ欠損率超過")
        exclude = True
    if row.get("ops_rate", 1) < min_ops:
        reasons.append("・稼働不足")
        exclude = True
    if row.get("waveform") == WaveformType.DEATH.value:
        reasons.append("・死亡型波形")
        exclude = True
    if row.get("long_negative_days", 0) >= 5:
        reasons.append("・店舗死に位置")
        exclude = True
    if island_row and island_row.get("island_recovery_signal"):
        if store_mode == StoreMode.RECOVERY:
            reasons.append("・回収周期一致（島）")
            exclude = True
    if row.get("hold_low_setting", 0):
        reasons.append("・据え置き低設定傾向")
        exclude = True
    if island_row and island_row.get("island_mean_diff", 0) < -800:
        reasons.append("・長期未投入島")
        exclude = True

    return exclude, reasons


def _build_positive_reasons(row: dict, store_mode: StoreMode, *, ev_mode: bool = True) -> list[str]:
    reasons: list[str] = []
    if not ev_mode:
        if row.get("sunk_days", 0) >= 2:
            reasons.append(f"・{int(row['sunk_days'])}日凹み後（放出期待）")
        if row.get("is_corner2"):
            reasons.append("・角2配置")
        elif row.get("is_corner"):
            reasons.append("・角配置")
    if row.get("specific_day_match"):
        reasons.append("・特定日一致")
    if row.get("island_boost"):
        reasons.append("・島全体強化傾向")
    wf = row.get("waveform")
    if not ev_mode:
        if wf == WaveformType.RIGHT_SHOULDER.value:
            reasons.append("・右肩型波形")
        elif wf == WaveformType.ONE_SHOT.value:
            reasons.append("・一撃型波形")
        elif wf == WaveformType.RELEASE.value:
            reasons.append("・放出型波形")
    elif wf == WaveformType.RELEASE.value:
        reasons.append("・放出型波形")
    if store_mode == StoreMode.RELEASE:
        reasons.append("・店舗放出モード")
    if row.get("past_match_rate", 0) >= 0.6:
        reasons.append("・過去同条件投入率高")
    if not reasons:
        reasons.append("・店舗営業パターンから相対高期待")
    return reasons


def analyze_store(
    df: pd.DataFrame,
    store_id: str,
    target_date: date,
    weights: LayerWeights | None = None,
    store_metadata: dict | None = None,
    *,
    ev_mode: bool = True,
    border_specs: list[BorderSpec] | None = None,
) -> list[dict]:
    w = weights or LayerWeights()
    if df.empty:
        return []

    df = enrich_island_column(df, store_id)
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    df["weekday"] = df["captured_at"].dt.weekday
    if "machine_number" not in df.columns:
        df["machine_number"] = 0

    meta = store_metadata or {}
    event_days = meta.get("event_days") or [3, 9]
    store_mode = detect_store_mode(df, target_date, event_days)
    island_stats = compute_island_stats(df, target_date)
    island_map = {r["island_id"]: r for r in island_stats.to_dict("records")} if not island_stats.empty else {}

    min_samples_slot = _store_min_samples(store_id, df, "slot")
    min_samples_pachi = _store_min_samples(store_id, df, "pachinko")

    results: list[dict] = []
    target_weekday = target_date.weekday()
    target_dom = target_date.day

    for machine_id, g in df.groupby("machine_id"):
        g = g.sort_values("captured_at")
        latest = g.iloc[-1]
        mn = int(latest.get("machine_number") or 0)
        island_id = latest.get("island_id")
        island_row = island_map.get(str(island_id)) if pd.notna(island_id) else None

        pos = latest.get("position_type") or infer_position(mn, island_id)
        is_corner = 1 if pos in ("corner", "corner2") else 0
        is_corner2 = 1 if pos == "corner2" else 0

        daily = g.groupby(g["captured_at"].dt.date)["diff_coins"].last().dropna()
        sunk_days = 0
        for v in reversed(daily.tolist()):
            if v < 0:
                sunk_days += 1
            else:
                break

        long_neg = sum(1 for v in daily.tolist()[-14:] if v < -500)
        recent7 = g[g["captured_at"].dt.date >= target_date - timedelta(days=7)]
        diff_range = 0.0
        if recent7["diff_coins"].notna().sum() >= 2:
            d = recent7["diff_coins"].dropna()
            diff_range = float(d.max() - d.min())
        hold_low = 1.0 if diff_range <= 400 and daily.mean() < -200 else 0.0

        # みんレポ等は回転数なし → 欠損率に含めない
        # パチンコは final_games 列が無いため diff_coins のみで評価
        gtype_row = latest.get("game_type") or classify_game_type(str(latest.get("title") or ""))
        miss_cols = ["diff_coins"]
        if gtype_row != "pachinko":
            miss_cols.append("final_games")
        if g["rotation_count"].notna().any():
            miss_cols.append("rotation_count")
        missing_rate = float(g[miss_cols].isna().mean().mean())
        ops_rate = float(g["is_operating"].mean()) if g["is_operating"].notna().any() else 0.5
        rot_mean = float(g["rotation_count"].dropna().mean()) if g["rotation_count"].notna().any() else 0.0

        wf = classify_waveform(g)
        ts = _time_slot_features(g)

        wd_hist = g[g["captured_at"].dt.weekday == target_weekday]
        dom_hist = g[g["captured_at"].dt.day == target_dom]
        past_match = 0.0
        for sub in (wd_hist, dom_hist):
            if len(sub) >= 5:
                dmean = sub.groupby(sub["captured_at"].dt.date)["diff_coins"].last().mean()
                if pd.notna(dmean) and dmean > 0:
                    past_match = max(past_match, 0.7 if sub is wd_hist else 0.5)

        specific_day = 1.0 if target_dom in event_days or (target_dom % 10) in event_days or past_match > 0 else 0.0
        island_boost = float(island_row.get("island_release_signal", 0)) if island_row else 0.0

        bev, bev_reasons, rot_per_k, border_exceeded = border_ev_score(
            g,
            mn,
            str(latest.get("title") or ""),
            gtype_row,
            target_date,
            meta,
            border_specs,
            store_df=df,
            island_id=str(island_id) if pd.notna(island_id) else None,
        )
        use_ocult = not ev_mode

        # 加重スコア（モード別補正）
        score = 50.0
        if use_ocult:
            score += min(sunk_days * 7, 21) * w.specific_day
            score += is_corner2 * 11 * w.position
            score += is_corner * 5 * w.position
            score += island_boost * 14 * w.island
            score += specific_day * 8 * w.specific_day
            score += past_match * 12
            score += (ts["evening_spike"] > 300) * 6 * w.time_slot
            score += (ts["open_hour_rot"] > 2000) * 4 * w.time_slot
            if wf == WaveformType.RIGHT_SHOULDER:
                score += 8 * w.waveform
            elif wf == WaveformType.ONE_SHOT:
                score += 10 * w.waveform
            elif wf == WaveformType.RELEASE:
                score += 7 * w.waveform
            elif wf == WaveformType.DEATH:
                score -= 25 * w.waveform
        else:
            # 期待値モード: 凹み・角・右肩は完全0点
            score += specific_day * 10 * w.specific_day
            score += past_match * 6
            score += bev * 28 * w.border_ev
            if border_exceeded:
                score += 12
            if wf == WaveformType.DEATH:
                score -= 10 * w.waveform

        if store_mode == StoreMode.RECOVERY:
            score -= 8
        elif store_mode == StoreMode.RELEASE:
            score += 6
        elif store_mode == StoreMode.EVENT:
            score += 4

        score -= missing_rate * 35
        score -= hold_low * 12 * w.exclusion_penalty
        score -= long_neg * 2 * w.exclusion_penalty
        if gtype_row == "pachinko" and use_ocult:
            score += 4
            if wf in (WaveformType.RELEASE, WaveformType.RIGHT_SHOULDER):
                score += 3

        score = float(np.clip(score, 0, 100))

        row = {
            "machine_id": int(machine_id),
            "sample_count": len(g),
            "missing_rate": missing_rate,
            "ops_rate": ops_rate,
            "sunk_days": sunk_days,
            "is_corner": is_corner,
            "is_corner2": is_corner2,
            "specific_day_match": specific_day,
            "island_boost": island_boost,
            "past_match_rate": past_match,
            "hold_low_setting": hold_low,
            "long_negative_days": long_neg,
            "waveform": wf.value,
            "rot_mean": rot_mean,
            "game_type": gtype_row,
        }

        min_n = min_samples_pachi if gtype_row == "pachinko" else min_samples_slot
        excluded, ex_reasons = _exclusion_checks(
            row, store_mode, island_row, gtype_row, min_samples=min_n
        )
        pos_reasons = _build_positive_reasons(row, store_mode, ev_mode=ev_mode)
        if ev_mode and bev_reasons:
            pos_reasons = (bev_reasons + pos_reasons)[:6]
        rec_min = settings.score_recommend_min - (4 if gtype_row == "pachinko" else 0)

        if excluded:
            tier = VerdictTier.EXCLUDE
            reasons = ex_reasons
        elif score >= rec_min:
            tier = VerdictTier.RECOMMEND
            reasons = pos_reasons
        elif score >= settings.score_hold_min:
            tier = VerdictTier.HOLD
            reasons = pos_reasons + ["・要確認（保留）"]
        else:
            tier = VerdictTier.EXCLUDE
            reasons = ["・低期待値"] + ex_reasons

        confidence = min(0.95, 0.35 + row["sample_count"] / 400 + past_match * 0.2)
        if missing_rate > 0.1:
            confidence *= 0.7

        title = str(latest.get("title") or "")
        gtype = latest.get("game_type") or classify_game_type(title)
        if gtype not in ("slot", "pachinko"):
            gtype = classify_game_type(title)

        results.append(
            {
                "machine_id": int(machine_id),
                "score": round(score, 1),
                "border_ev": round(bev, 3),
                "rot_per_1000_yen": round(rot_per_k, 2) if rot_per_k is not None else None,
                "border_exceeded": border_exceeded,
                "tier": tier.value,
                "reasons": reasons[:6],
                "sample_count": row["sample_count"],
                "period_days": 90,
                "confidence": round(confidence, 2),
                "has_missing_data": missing_rate > 0.1,
                "store_mode": store_mode.value,
                "waveform": wf.value,
                "island_id": str(island_id) if pd.notna(island_id) else None,
                "game_type": gtype,
            }
        )

    def _tier_slice(game_type: str, n_rec: int = 20, n_hold: int = 15, n_ex: int = 30) -> list[dict]:
        subset = [r for r in results if r.get("game_type") == game_type]
        def _sort_key(x: dict) -> tuple:
            if not ev_mode:
                return (x["score"], x.get("border_ev", 0))
            return (
                1 if x.get("border_exceeded") else 0,
                x.get("rot_per_1000_yen") or 0,
                x.get("border_ev", 0),
                x["score"],
            )

        recs = sorted(
            [r for r in subset if r["tier"] == VerdictTier.RECOMMEND.value],
            key=_sort_key,
            reverse=True,
        )
        holds_pool = sorted(
            [r for r in subset if r["tier"] == VerdictTier.HOLD.value],
            key=_sort_key,
            reverse=True,
        )
        if len(recs) < n_rec and holds_pool:
            need = n_rec - len(recs)
            promoted = holds_pool[:need]
            for r in promoted:
                r["tier"] = VerdictTier.RECOMMEND.value
                r["reasons"] = list(r.get("reasons", [])) + ["・期待値繰上（厳選）"]
            recs = recs + promoted
            holds_pool = holds_pool[need:]
        recs = recs[:n_rec]
        for i, r in enumerate(recs, 1):
            r["rank"] = i

        holds = holds_pool[:n_hold]
        for i, r in enumerate(holds, 1):
            r["rank"] = 1000 + i

        excludes = sorted(
            [r for r in subset if r["tier"] == VerdictTier.EXCLUDE.value],
            key=lambda x: x["score"],
            reverse=True,
        )[:n_ex]
        for i, r in enumerate(excludes, 1):
            r["rank"] = 9000 + i

        return recs + holds + excludes

    return _tier_slice("slot") + _tier_slice("pachinko")
