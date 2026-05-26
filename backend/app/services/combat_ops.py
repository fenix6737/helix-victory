"""実戦運用オーケストレーション — 監査・モード・検証の統合"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.anomaly_guardian import detect_anomalies
from app.analysis.combat_history import save_combat_snapshot
from app.analysis.combat_mode_engine import resolve_combat_mode
from app.analysis.ev_validation_engine import validate_ev_performance
from app.analysis.integrity_guardian import audit_data_integrity
from app.analysis.drift_detection import detect_feature_drift
from app.analysis.manager_shift_detector import detect_manager_shift
from app.analysis.online_learning_engine import get_learning_summary, run_online_learning
from app.analysis.recovery_engine import check_system_health
from app.cache import cache_set
from app.models import Machine, RawLog, Store, StoreDailyInsight
from app.timeutil import analysis_target_date, jst_now


async def load_store_df(db: AsyncSession, store_id: str, days: int = 90) -> pd.DataFrame:
    since = jst_now().astimezone(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            RawLog.machine_id,
            RawLog.machine_number,
            RawLog.captured_at,
            RawLog.diff_coins,
            RawLog.rotation_count,
            RawLog.is_operating,
            Machine.title,
            Machine.island_id,
            Machine.game_type,
        )
        .join(Machine, Machine.id == RawLog.machine_id)
        .where(RawLog.store_id == store_id, RawLog.captured_at >= since)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        rows,
        columns=[
            "machine_id",
            "machine_number",
            "captured_at",
            "diff_coins",
            "rotation_count",
            "is_operating",
            "title",
            "island_id",
            "game_type",
        ],
    )


async def run_combat_status(
    db: AsyncSession,
    store_id: str,
    scored: list[dict] | None = None,
    danger_level: str = "safe",
    danger_score: float = 0.0,
    should_play: bool = True,
    playable_count: int = 0,
    store_mode: str | None = None,
) -> dict:
    target = analysis_target_date()
    df = await load_store_df(db, store_id)
    hist_days = 30
    cutoff = jst_now().astimezone(timezone.utc) - timedelta(days=hist_days)
    hist_df = df[pd.to_datetime(df["captured_at"], utc=True) < cutoff] if not df.empty else df
    recent_df = df[pd.to_datetime(df["captured_at"], utc=True) >= cutoff] if not df.empty else df

    integrity = audit_data_integrity(df, store_id)
    insight_row = await db.get(StoreDailyInsight, (store_id, target))
    prior_audit = json.loads(insight_row.feature_audit_json) if insight_row else {}
    manager = detect_manager_shift(hist_df, recent_df, prior_audit)
    anomaly = detect_anomalies(scored or [], df, integrity)
    ev_val = await validate_ev_performance(db, store_id, target)
    learning = await get_learning_summary(db, store_id)
    health = await check_system_health()

    drift_feat = detect_feature_drift(hist_df, recent_df, prior_audit)
    drift_score = float(drift_feat.get("drift_score", 0))

    combat = resolve_combat_mode(
        danger_level=danger_level,
        danger_score=danger_score,
        should_play=should_play and not anomaly.get("block_recommendations"),
        integrity_ok=integrity.get("allow_analysis", True),
        anomaly_block=anomaly.get("block_recommendations", False),
        manager_shift_prob=float(manager.get("operation_change_probability", 0)),
        playable_count=playable_count,
        store_mode=store_mode,
        drift_score=drift_score,
        force_retreat=False,
    )

    out = {
        "store_id": store_id,
        "target_date": target.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "combat_mode": combat.to_dict(),
        "integrity": integrity,
        "anomaly": anomaly,
        "manager_shift": manager,
        "ev_validation": ev_val,
        "online_learning": learning,
        "system_health": health,
        "allow_recommendations": integrity.get("allow_analysis")
        and not anomaly.get("block_recommendations")
        and combat.should_play,
    }

    save_combat_snapshot(store_id, target, out)
    await cache_set(f"combat_status:{store_id}:{target.isoformat()}", out, 60)
    return out


async def pre_analysis_gate(db: AsyncSession, store_id: str) -> dict:
    """分析前ゲート — NGなら分析しない"""
    df = await load_store_df(db, store_id, days=30)
    integrity = audit_data_integrity(df, store_id)
    if not integrity.get("allow_analysis"):
        return {"blocked": True, "integrity": integrity}
    return {"blocked": False, "integrity": integrity}


async def post_analysis_hooks(
    db: AsyncSession,
    store_id: str,
    scored: list[dict],
    danger_level: str,
    danger_score: float,
    should_play: bool,
    store_mode: str | None,
) -> dict:
    playable = sum(1 for s in scored if s.get("tier") == "recommend")
    status = await run_combat_status(
        db,
        store_id,
        scored=scored,
        danger_level=danger_level,
        danger_score=danger_score,
        should_play=should_play,
        playable_count=playable,
        store_mode=store_mode,
    )
    return status
