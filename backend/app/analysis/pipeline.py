import json
from datetime import date, datetime, timedelta, timezone

from app.timeutil import analysis_target_date, jst_now, jst_today

import pandas as pd
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.engine import LayerWeights, analyze_store
from app.analysis.feedback import adjust_weights, record_outcomes
from app.analysis.island import enrich_island_column
from app.cache import cache_delete_pattern
from app.models import AnalysisWeights, Machine, RawLog, Recommendation, StoreMetadata
from app.analysis.anomaly_guardian import detect_anomalies
from app.analysis.integrity_guardian import audit_data_integrity
from app.analysis.online_learning_engine import run_online_learning
from app.services.combat_ops import post_analysis_hooks, pre_analysis_gate
from app.services.store_insights import build_and_save_insights


async def _load_weights(db: AsyncSession, store_id: str) -> LayerWeights:
    row = await db.get(AnalysisWeights, store_id)
    if row:
        return LayerWeights.from_dict(json.loads(row.weights_json))
    return LayerWeights()


async def run_analysis(
    db: AsyncSession,
    store_id: str,
    target_date: date | None = None,
    *,
    run_feedback: bool = True,
) -> dict:
    target = target_date or analysis_target_date()
    since = jst_now().astimezone(timezone.utc) - timedelta(days=90)

    if run_feedback:
        await record_outcomes(db, store_id, jst_today())
        await adjust_weights(db, store_id)

    stmt = (
        select(
            RawLog.machine_id,
            RawLog.machine_number,
            RawLog.captured_at,
            RawLog.diff_coins,
            RawLog.rotation_count,
            RawLog.big_count,
            RawLog.reg_count,
            RawLog.final_games,
            RawLog.graph_samples_json,
            RawLog.is_operating,
            Machine.position_type,
            Machine.island_id,
            Machine.title,
            Machine.game_type,
        )
        .join(Machine, Machine.id == RawLog.machine_id)
        .where(RawLog.store_id == store_id, RawLog.captured_at >= since)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return {"recommendations_created": 0, "tier_counts": {}, "blocked": False}

    gate = await pre_analysis_gate(db, store_id)
    if gate.get("blocked"):
        return {
            "recommendations_created": 0,
            "tier_counts": {},
            "blocked": True,
            "integrity": gate.get("integrity"),
        }

    df = pd.DataFrame(
        rows,
        columns=[
            "machine_id",
            "machine_number",
            "captured_at",
            "diff_coins",
            "rotation_count",
            "big_count",
            "reg_count",
            "final_games",
            "graph_samples_json",
            "is_operating",
            "position_type",
            "island_id",
            "title",
            "game_type",
        ],
    )
    df = enrich_island_column(df, store_id)

    weights = await _load_weights(db, store_id)
    meta_row = await db.get(StoreMetadata, store_id)
    store_meta = json.loads(meta_row.metadata_json) if meta_row else {}
    integrity = audit_data_integrity(df, store_id)
    from app.services.analysis_settings import get_ev_mode
    from app.services.machine_border_service import list_borders

    ev_mode = await get_ev_mode(db, store_id)
    borders = await list_borders(db)
    scored = analyze_store(
        df, store_id, target, weights, store_meta, ev_mode=ev_mode, border_specs=borders
    )
    anomaly = detect_anomalies(scored, df, integrity)
    if anomaly.get("block_recommendations"):
        for s in scored:
            if s.get("tier") == "recommend":
                s["tier"] = "hold"
                s["reasons"] = ["・異常検知により推奨停止"] + (s.get("reasons") or [])

    await db.execute(
        delete(Recommendation).where(
            Recommendation.store_id == store_id,
            Recommendation.target_date == target,
        )
    )

    tier_counts: dict[str, int] = {"recommend": 0, "hold": 0, "exclude": 0}
    for item in scored:
        tier = item.get("tier", "exclude")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

        if item.get("island_id"):
            machine = await db.get(Machine, item["machine_id"])
            if machine and not machine.island_id:
                machine.island_id = item["island_id"]

        rec = Recommendation(
            store_id=store_id,
            machine_id=item["machine_id"],
            target_date=target,
            rank=item.get("rank", 9999),
            tier=tier,
            score=item["score"],
            reasons=json.dumps(item["reasons"], ensure_ascii=False),
            sample_count=item["sample_count"],
            period_days=item["period_days"],
            confidence=item["confidence"],
            has_missing_data=item["has_missing_data"],
            store_mode=item.get("store_mode"),
            waveform=item.get("waveform"),
            model_version="engine_v2",
        )
        db.add(rec)

    insight = await build_and_save_insights(db, store_id, df, scored, weights, target)

    if run_feedback:
        await run_online_learning(db, store_id, datetime.now(timezone.utc).date())

    combat = await post_analysis_hooks(
        db,
        store_id,
        scored,
        insight.danger_level,
        insight.danger_score,
        insight.should_play,
        insight.store_mode,
    )

    await db.commit()
    await cache_delete_pattern(f"ranking:{store_id}:*")
    await cache_delete_pattern(f"machine_stats:*")

    return {
        "recommendations_created": len(scored),
        "tier_counts": tier_counts,
        "target_date": target.isoformat(),
        "danger_level": insight.danger_level,
        "should_play": insight.should_play,
        "feature_alerts": insight.feature_audit.get("alerts", []),
        "combat_mode": combat.get("combat_mode"),
        "allow_recommendations": combat.get("allow_recommendations"),
        "integrity_ok": integrity.get("ok"),
        "anomaly_alerts": anomaly.get("alerts", []),
        "blocked": False,
    }


async def migrate_schema(engine) -> None:
    """既存DBへのカラム追加（本番起動時）"""
    statements_sqlite = [
        "ALTER TABLE machines ADD COLUMN game_type VARCHAR(16) DEFAULT 'slot'",
        """CREATE TABLE IF NOT EXISTS store_daily_insights (
            store_id VARCHAR(32) NOT NULL,
            target_date DATE NOT NULL,
            danger_level VARCHAR(16) DEFAULT 'safe',
            danger_score REAL DEFAULT 0,
            should_play BOOLEAN DEFAULT 1,
            headline VARCHAR(256) DEFAULT '',
            danger_reasons_json TEXT DEFAULT '[]',
            feature_audit_json TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (store_id, target_date)
        )""",
        """CREATE TABLE IF NOT EXISTS play_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id VARCHAR(32) NOT NULL,
            machine_id INTEGER,
            machine_number INTEGER NOT NULL,
            title VARCHAR(128) DEFAULT '',
            game_type VARCHAR(16) DEFAULT 'slot',
            invest_yen INTEGER DEFAULT 0,
            result_yen INTEGER DEFAULT 0,
            note VARCHAR(256) DEFAULT '',
            played_at TIMESTAMP,
            created_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS daily_prediction_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id VARCHAR(32) NOT NULL,
            target_date DATE NOT NULL,
            report_json TEXT NOT NULL,
            hit_summary_json TEXT,
            data_sources_json TEXT,
            generated_at TIMESTAMP,
            UNIQUE(store_id, target_date)
        )""",
        """CREATE TABLE IF NOT EXISTS m_machine_borders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_pattern VARCHAR(128) NOT NULL,
            border_per_1000_yen REAL NOT NULL,
            game_type VARCHAR(16) DEFAULT 'pachinko',
            coin_price_yen REAL DEFAULT 4.0,
            base_games INTEGER DEFAULT 400,
            updated_at TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS store_analysis_settings (
            store_id VARCHAR(32) PRIMARY KEY,
            ev_mode BOOLEAN DEFAULT 1,
            updated_at TIMESTAMP
        )""",
        "ALTER TABLE raw_logs ADD COLUMN graph_samples_json TEXT",
    ]
    if engine.dialect.name == "sqlite":
        async with engine.begin() as conn:
            for sql in statements_sqlite:
                try:
                    await conn.execute(text(sql))
                except Exception:
                    pass
        return

    statements = [
        "ALTER TABLE machines ADD COLUMN IF NOT EXISTS game_type VARCHAR(16) DEFAULT 'slot'",
        "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS tier VARCHAR(16) DEFAULT 'recommend'",
        "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS store_mode VARCHAR(32)",
        "ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS waveform VARCHAR(32)",
        """CREATE TABLE IF NOT EXISTS store_metadata (
            store_id VARCHAR(32) PRIMARY KEY REFERENCES stores(id),
            metadata_json TEXT NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS store_daily_insights (
            store_id VARCHAR(32) NOT NULL REFERENCES stores(id),
            target_date DATE NOT NULL,
            danger_level VARCHAR(16) DEFAULT 'safe',
            danger_score DOUBLE PRECISION DEFAULT 0,
            should_play BOOLEAN DEFAULT TRUE,
            headline VARCHAR(256) DEFAULT '',
            danger_reasons_json TEXT DEFAULT '[]',
            feature_audit_json TEXT DEFAULT '{}',
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (store_id, target_date)
        )""",
        """CREATE TABLE IF NOT EXISTS play_records (
            id SERIAL PRIMARY KEY,
            store_id VARCHAR(32) NOT NULL REFERENCES stores(id),
            machine_id INTEGER REFERENCES machines(id),
            machine_number INTEGER NOT NULL,
            title VARCHAR(128) DEFAULT '',
            game_type VARCHAR(16) DEFAULT 'slot',
            invest_yen INTEGER DEFAULT 0,
            result_yen INTEGER DEFAULT 0,
            note VARCHAR(256) DEFAULT '',
            played_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS daily_prediction_reports (
            id SERIAL PRIMARY KEY,
            store_id VARCHAR(32) NOT NULL REFERENCES stores(id),
            target_date DATE NOT NULL,
            report_json TEXT NOT NULL,
            hit_summary_json TEXT,
            data_sources_json TEXT,
            generated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(store_id, target_date)
        )""",
        """CREATE TABLE IF NOT EXISTS m_machine_borders (
            id SERIAL PRIMARY KEY,
            title_pattern VARCHAR(128) NOT NULL,
            border_per_1000_yen DOUBLE PRECISION NOT NULL,
            game_type VARCHAR(16) DEFAULT 'pachinko',
            coin_price_yen DOUBLE PRECISION DEFAULT 4.0,
            base_games INTEGER DEFAULT 400,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS store_analysis_settings (
            store_id VARCHAR(32) PRIMARY KEY REFERENCES stores(id),
            ev_mode BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
        "ALTER TABLE raw_logs ADD COLUMN IF NOT EXISTS graph_samples_json TEXT",
    ]
    async with engine.begin() as conn:
        for sql in statements:
            await conn.execute(text(sql))
