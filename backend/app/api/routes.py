import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.pipeline import run_analysis
from app.auth import create_access_token, require_admin, require_admin_or_ingest_key, verify_admin_credentials
from app.config import settings
from app.db import get_db
from app.schemas import (
    AnalysisRunRequest,
    DailyLearningCycleOut,
    DailyLoopRequest,
    DailyPredictionReportOut,
    IngestResult,
    PeriodStatisticsOut,
    LoginRequest,
    MachineDetailOut,
    RawLogIngestRequest,
    StoreOut,
    TokenOut,
    StoreDailyInsightOut,
    CombatStatusOut,
    StoreLiveEvOut,
    StoreLiveStatusOut,
    TodayRecommendationsOut,
    PerformanceDashboardOut,
    StoreExtrasOut,
    PlayRecordIn,
    PlayRecordOut,
)
from app.models import StoreMetadata
from app.services import (
    combat_ops,
    daily_cycle,
    ingest,
    live_ev,
    live_status,
    period_statistics,
    performance_stats,
    play_records,
    prediction_report,
    recommendations,
    store_extras,
    store_insights,
)

router = APIRouter(prefix="/api/v1")


@router.post("/auth/login", response_model=TokenOut)
async def login(body: LoginRequest):
    if not verify_admin_credentials(body.username, body.password):
        raise HTTPException(401, "IDまたはパスワードが正しくありません")
    token = create_access_token(body.username)
    return TokenOut(
        access_token=token,
        expires_hours=settings.jwt_expire_hours,
    )


@router.get("/stores", response_model=list[StoreOut])
async def get_stores(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    stores = await recommendations.list_stores(db)
    return [StoreOut(id=s.id, name=s.name, is_active=s.is_active) for s in stores]


@router.get("/recommendations/today", response_model=TodayRecommendationsOut)
async def get_today_recommendations(
    store_id: str = Query(...),
    target_date: date | None = None,
    game_type: str = Query("all", pattern="^(all|slot|pachinko)$"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = await recommendations.get_today_recommendations(
        db, store_id, target_date, game_type=game_type
    )
    if out is None:
        raise HTTPException(404, "店舗が見つかりません")
    return out


@router.get("/stores/{store_id}/live-status", response_model=StoreLiveStatusOut)
async def get_live_status(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return await live_status.get_store_live_status(db, store_id)


@router.get("/stores/{store_id}/combat-status", response_model=CombatStatusOut)
async def get_combat_status(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = await combat_ops.run_combat_status(db, store_id)
    return CombatStatusOut(**out)


@router.get("/health/combat")
async def get_combat_health():
    from app.analysis.recovery_engine import check_system_health

    return await check_system_health()


@router.get("/stores/{store_id}/live-ev", response_model=StoreLiveEvOut)
async def get_store_live_ev(
    store_id: str,
    target_date: date | None = None,
    game_type: str = Query("all", pattern="^(all|slot|pachinko)$"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = await live_ev.get_store_live_ev(db, store_id, game_type, target_date)
    if out is None:
        raise HTTPException(404, "リアルタイム期待値を計算できません（データ不足）")
    return out


@router.get("/stores/{store_id}/insights/today", response_model=StoreDailyInsightOut)
async def get_store_insights_today(
    store_id: str,
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = await store_insights.get_daily_insight(db, store_id, target_date)
    if out is None:
        raise HTTPException(404, "本日の店舗インサイトがありません。分析を実行してください。")
    return out


@router.get("/stores/{store_id}/performance", response_model=PerformanceDashboardOut)
async def get_store_performance(
    store_id: str,
    game_type: str = Query("all", pattern="^(all|slot|pachinko)$"),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = await performance_stats.get_performance_dashboard(db, store_id, game_type)
    return PerformanceDashboardOut(**data)


@router.get("/stores/{store_id}/extras", response_model=StoreExtrasOut)
async def get_store_extras(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = await store_extras.get_store_extras(db, store_id)
    return StoreExtrasOut(**data)


@router.get("/stores/{store_id}/play-records", response_model=list[PlayRecordOut])
async def get_play_records(
    store_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return await play_records.list_play_records(db, store_id, limit)


@router.post("/stores/{store_id}/play-records", response_model=PlayRecordOut)
async def post_play_record(
    store_id: str,
    body: PlayRecordIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    if body.store_id != store_id:
        raise HTTPException(400, "store_id mismatch")
    return await play_records.create_play_record(db, body)


@router.delete("/play-records/{record_id}")
async def delete_play_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    ok = await play_records.delete_play_record(db, record_id)
    if not ok:
        raise HTTPException(404, "記録が見つかりません")
    return {"deleted": True}


@router.post("/stores/{store_id}/backfill-game-types")
async def post_backfill_game_types(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    n = await recommendations.backfill_machine_game_types(db, store_id)
    return {"store_id": store_id, "updated": n}


@router.get("/machines/{machine_id}", response_model=MachineDetailOut)
async def get_machine_detail(
    machine_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    out = await recommendations.get_machine_detail(db, machine_id)
    if out is None:
        raise HTTPException(404, "台が見つかりません")
    return out


class StoreMetadataIn(BaseModel):
    event_days: list[int] = []
    anniversary: str | None = None
    slot_count: int | None = None
    source_url: str | None = None
    data_sources: dict | None = None
    hall_navi: dict | None = None
    updated_at: str | None = None


@router.post("/stores/{store_id}/metadata")
async def post_store_metadata(
    store_id: str,
    body: StoreMetadataIn,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin_or_ingest_key),
):
    row = await db.get(StoreMetadata, store_id)
    payload = body.model_dump()
    if row:
        row.metadata_json = json.dumps(payload, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(
            StoreMetadata(
                store_id=store_id,
                metadata_json=json.dumps(payload, ensure_ascii=False),
            )
        )
    await db.commit()
    return {"store_id": store_id, "ok": True}


@router.get("/stores/{store_id}/metadata")
async def get_store_metadata(
    store_id: str,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = await db.get(StoreMetadata, store_id)
    if not row:
        return {}
    return json.loads(row.metadata_json)


@router.post("/ingest/logs", response_model=IngestResult)
async def post_ingest_logs(
    body: RawLogIngestRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin_or_ingest_key),
):
    inserted, skipped = await ingest.ingest_logs(db, body.store_id, body.logs)
    return IngestResult(inserted=inserted, skipped=skipped)


@router.post("/analysis/run")
async def post_analysis_run(
    body: AnalysisRunRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return await run_analysis(db, body.store_id, body.target_date, run_feedback=body.run_feedback)


@router.post("/analysis/daily-loop")
async def post_daily_loop(
    body: DailyLoopRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """予測検証 + 重み調整 + 翌日分析（日次バッチ用）"""
    return await run_analysis(db, body.store_id, run_feedback=True)


@router.post("/analysis/daily-learning-cycle", response_model=DailyLearningCycleOut)
async def post_daily_learning_cycle(
    body: DailyLoopRequest,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """日次学習サイクル（照合→再学習→予測→レポート保存）"""
    result = await daily_cycle.run_daily_learning_cycle(db, body.store_id)
    return DailyLearningCycleOut(store_id=body.store_id, result=result)


@router.get("/stores/{store_id}/prediction-report", response_model=DailyPredictionReportOut)
async def get_prediction_report(
    store_id: str,
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    report = await prediction_report.get_latest_report(db, store_id, target_date)
    if not report:
        raise HTTPException(404, "予測レポートがありません。日次サイクルを実行してください。")
    return DailyPredictionReportOut(
        store_id=store_id,
        target_date=target_date,
        report=report,
    )


@router.get("/stores/{store_id}/statistics/daily", response_model=PeriodStatisticsOut)
async def get_stats_daily(
    store_id: str,
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = await period_statistics.get_daily_statistics(db, store_id, target_date)
    return PeriodStatisticsOut(store_id=store_id, period="daily", data=data)


@router.get("/stores/{store_id}/statistics/weekly", response_model=PeriodStatisticsOut)
async def get_stats_weekly(
    store_id: str,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = await period_statistics.get_weekly_statistics(db, store_id, end_date)
    return PeriodStatisticsOut(store_id=store_id, period="weekly", data=data)


@router.get("/stores/{store_id}/statistics/monthly", response_model=PeriodStatisticsOut)
async def get_stats_monthly(
    store_id: str,
    year: int | None = None,
    month: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
):
    data = await period_statistics.get_monthly_statistics(db, store_id, year, month)
    return PeriodStatisticsOut(store_id=store_id, period="monthly", data=data)
