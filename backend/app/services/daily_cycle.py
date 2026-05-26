"""日次学習サイクル — 取得→予測→照合→的中率→再学習（開発者指示書 2-2）"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.feedback import adjust_weights, record_outcomes
from app.analysis.pipeline import run_analysis
from app.models import AnalysisWeights, StoreMetadata
from app.services.prediction_report import (
    build_and_save_daily_report,
    update_report_hit_summary,
)
from app.timeutil import analysis_target_date, jst_today


async def _load_data_sources(db: AsyncSession, store_id: str) -> dict:
    row = await db.get(StoreMetadata, store_id)
    if not row:
        return {}
    try:
        meta = json.loads(row.metadata_json)
        return meta.get("data_sources") or {}
    except json.JSONDecodeError:
        return {}


async def run_daily_learning_cycle(
    db: AsyncSession,
    store_id: str,
    *,
    target_date: date | None = None,
    skip_analysis: bool = False,
) -> dict:
    """
    深夜0時以降に実行する統合バッチ。
    1. 前日予測と当日実績の照合
    2. 重み再学習
    3. 翌日（対象日）の予測生成
    4. レポート保存
    """
    today = jst_today()
    target = target_date or analysis_target_date()
    eval_date = today

    outcomes = await record_outcomes(db, store_id, eval_date)
    await update_report_hit_summary(db, store_id, eval_date)
    await adjust_weights(db, store_id)
    wrow = await db.get(AnalysisWeights, store_id)
    hit_rate_14d = wrow.hit_rate_14d if wrow else None

    analysis_result = {"recommendations_created": 0, "blocked": False}
    if not skip_analysis:
        analysis_result = await run_analysis(
            db, store_id, target_date=target, run_feedback=False
        )

    sources = await _load_data_sources(db, store_id)
    report = await build_and_save_daily_report(
        db, store_id, target, data_sources=sources
    )

    return {
        "store_id": store_id,
        "eval_date": eval_date.isoformat(),
        "target_date": target.isoformat(),
        "outcomes_recorded": outcomes,
        "hit_rate_14d": hit_rate_14d,
        "analysis": analysis_result,
        "report": {
            "prediction_count": report.get("prediction_count"),
            "featured_count": report.get("featured_count"),
            "missing_sources": report.get("missing_sources"),
        },
        "cycle_completed_at": datetime.now(timezone.utc).isoformat(),
    }
