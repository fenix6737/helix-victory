from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_hours: int


class StoreOut(BaseModel):
    id: str
    name: str
    is_active: bool


TierType = Literal["recommend", "hold", "exclude"]
GameType = Literal["slot", "pachinko", "all"]


class RecommendationItem(BaseModel):
    rank: int
    machine_id: int
    title: str
    machine_number: int
    score: float = Field(description="推奨スコア（相対評価）")
    tier: TierType = "recommend"
    reasons: list[str]
    sample_count: int
    period_days: int
    confidence: float
    has_missing_data: bool
    store_mode: str | None = None
    waveform: str | None = None
    game_type: str = "slot"
    icon_variant: str = "slot"
    expected_investment: float | None = None
    max_risk_line: float | None = None
    low_risk_zone: float | None = None
    deep_hole_probability: float | None = None
    island_id: str | None = None
    position_type: str | None = None
    week_diff_total: int | None = Field(
        default=None, description="直近7日の差枚合計（参考）"
    )
    is_featured: bool = False
    featured_group: str | None = None
    featured_badge: str | None = None
    spec_summary: str | None = None
    spec_lines: list[str] = []
    daily_big_count: int | None = Field(
        default=None, description="当日BB（最新スナップショット）"
    )
    daily_reg_count: int | None = Field(
        default=None, description="当日RB（最新スナップショット）"
    )
    daily_atari_total: int | None = Field(
        default=None, description="当日総当たり BB+RB"
    )


class TodayRecommendationsOut(BaseModel):
    store_id: str
    store_name: str
    target_date: date
    generated_at: datetime
    store_mode: str | None = None
    recommend: list[RecommendationItem] = []
    hold: list[RecommendationItem] = []
    exclude_preview: list[RecommendationItem] = []
    items: list[RecommendationItem] = []
    slot_recommend: int = 0
    slot_hold: int = 0
    pachinko_recommend: int = 0
    pachinko_hold: int = 0


class CombatStatusOut(BaseModel):
    store_id: str
    target_date: date
    generated_at: datetime
    combat_mode: dict
    integrity: dict
    anomaly: dict
    manager_shift: dict = {}
    ev_validation: dict = {}
    online_learning: dict = {}
    system_health: dict = {}
    allow_recommendations: bool = True


class LiveEvMachineOut(BaseModel):
    rank: int
    machine_id: int
    machine_number: int
    title: str
    game_type: str = "slot"
    icon_variant: str = "slot"
    morning_score: float
    current_ev: float
    exhaustion_rate: float = 0.0
    ev_delta: float = 0.0
    playable: bool = True
    seat_status: str = "playing"
    seat_label: str = ""
    waveform_ml_class: str = ""
    island_id: str | None = None
    reasons: list[str] = []
    expected_investment: float | None = None
    max_risk_line: float | None = None
    deep_hole_probability: float | None = None
    death_line: float | None = None
    recommend_score: float | None = None
    retreat_score: float | None = None


class StoreLiveEvOut(BaseModel):
    store_id: str
    store_name: str
    target_date: date
    generated_at: datetime
    should_play: bool
    danger_level: str
    danger_score: float
    danger_headline: str
    danger_reasons: list[str] = []
    drift_alerts: list[str] = []
    primary: LiveEvMachineOut | None = None
    alternatives: list[LiveEvMachineOut] = []
    playable_count: int = 0
    ranked_preview: list[LiveEvMachineOut] = []
    hot_islands: list[dict] = []
    quantile: dict = {}
    combat_mode: dict | None = None
    manager_warning: str | None = None
    deep_risk: bool = False
    islands_live: list[dict] = []
    recommend_score: float = 0.0
    retreat_score: float = 0.0
    collapse_probability: float = 0.0
    island_state: str = "neutral"
    retreat_reason: list[str] = []
    death_line: float = 0.0
    expected_investment: float = 0.0
    fake_release: bool = False
    trap_wave: bool = False
    watched: bool = False
    data_freshness_sec: int | None = None
    confidence: float = 1.0
    stale_warning: bool = False
    cache_degraded: bool = False
    recent_drift: float = 0.0
    deep_harami: bool = False
    median_ev: float | None = None
    downside_ev: float | None = None
    worst_case_ev: float | None = None


class StoreDailyInsightOut(BaseModel):
    store_id: str
    target_date: date
    danger_level: str  # safe | caution | danger | critical
    danger_score: float
    should_play: bool
    headline: str
    danger_reasons: list[str] = []
    feature_audit: dict = {}
    store_mode: str | None = None


class TierPerformanceBlock(BaseModel):
    sample_days: int = 0
    prediction_count: int = 0
    plus_count: int = 0
    plus_rate_pct: float | None = None
    avg_diff: float | None = None


class TierPerformanceWithTrend(BaseModel):
    days_7: TierPerformanceBlock
    days_30: TierPerformanceBlock
    daily_7: list[dict] = []


class PerformanceOperations(BaseModel):
    last_ingest_at: str | None = None
    last_analysis_at: str | None = None
    logs_24h: int = 0
    is_stale: bool = False
    has_data: bool = False
    outcomes_total: int = 0


class PerformanceDashboardOut(BaseModel):
    store_id: str
    game_type: str
    generated_at: datetime
    definition: str
    last_reconcile_count: int = 0
    recommend: TierPerformanceWithTrend
    hold: dict
    operations: PerformanceOperations
    disclaimer: str
    target_plus_rate_pct: float = 55.0
    ev_mode: bool = True


class AnalysisSettingsOut(BaseModel):
    store_id: str
    ev_mode: bool
    ev_mode_label: str


class AnalysisSettingsIn(BaseModel):
    ev_mode: bool


class MachineBorderOut(BaseModel):
    id: int
    title_pattern: str
    border_per_1000_yen: float
    game_type: str
    coin_price_yen: float
    base_games: int


class MachineBorderImportIn(BaseModel):
    csv_text: str
    replace: bool = False


class CollectorHealthOut(BaseModel):
    status: str
    level: str
    message: str
    sources_24h: dict[str, int] = {}
    active_sources: list[str] = []
    daidata_connected: bool = False


class InsightTrendOut(BaseModel):
    posture: str
    posture_label: str
    summary: str
    danger_score: float | None = None
    score_delta: float | None = None
    should_play: bool | None = None
    headline: str | None = None
    store_mode: str | None = None


class IslandHeatmapCell(BaseModel):
    island_id: str
    label: str
    machine_count: int
    mean_diff: int
    ops_rate: float
    temperature: str


class EventCalendarDay(BaseModel):
    date: str
    day: int
    weekday: int
    is_event_day: bool
    is_target: bool
    expectancy_level: str = "neutral"
    expectancy_score: int = 50
    label: str = "様子見"


class EventCalendarOut(BaseModel):
    target_date: str
    event_days: list[int]
    store_mode: str | None
    store_mode_label: str
    days: list[EventCalendarDay]


class StoreExtrasOut(BaseModel):
    store_id: str
    collector: CollectorHealthOut
    trend: InsightTrendOut
    islands: list[IslandHeatmapCell]
    events: EventCalendarOut


class PlayRecordIn(BaseModel):
    store_id: str
    machine_id: int | None = None
    machine_number: int
    title: str = ""
    game_type: str = "slot"
    invest_yen: int = 0
    result_yen: int = 0
    note: str = ""


class PlayRecordOut(BaseModel):
    id: int
    store_id: str
    machine_id: int | None
    machine_number: int
    title: str
    game_type: str
    invest_yen: int
    result_yen: int
    note: str
    played_at: datetime
    net_yen: int = 0


class StoreLiveStatusOut(BaseModel):
    ingest_age_minutes: int | None = None
    sync_age_minutes: int | None = None
    analysis_age_minutes: int | None = None
    is_analysis_stale: bool = False
    realtime_mode: str = "collect_then_analyze"
    store_id: str
    last_ingest_at: datetime | None
    last_sync_at: datetime | None = None
    last_analysis_at: datetime | None
    log_count_24h: int
    machine_count: int
    slot_count: int
    pachinko_count: int
    poll_interval_sec: int = 30
    is_stale: bool = False
    has_any_data: bool = False


class TimeSeriesPoint(BaseModel):
    captured_at: datetime
    diff_coins: int | None
    rotation_count: int | None
    big_count: int | None
    reg_count: int | None
    final_games: int | None
    is_operating: bool | None


class MachineDetailOut(BaseModel):
    machine_id: int
    store_id: str
    store_name: str
    machine_number: int
    title: str
    island_id: str | None
    position_type: str | None
    score: float | None
    tier: str | None = None
    reasons: list[str]
    sample_count: int
    period_days: int
    confidence: float
    has_missing_data: bool
    store_mode: str | None = None
    waveform: str | None = None
    time_series: list[TimeSeriesPoint]
    sunk_days: int | None = None
    hold_trend: str | None = None
    island_injection_history: str | None = None
    day_affinity: str | None = None
    game_type: str = "slot"
    spec_lines: list[str] = []
    daily_big_count: int | None = None
    daily_reg_count: int | None = None
    daily_atari_total: int | None = None


class RawLogIngestItem(BaseModel):
    machine_number: int
    title: str
    captured_at: datetime
    diff_coins: int | None = None
    rotation_count: int | None = None
    big_count: int | None = None
    reg_count: int | None = None
    final_games: int | None = None
    graph_url: str | None = None
    graph_samples_json: str | None = None
    is_operating: bool | None = None
    island_id: str | None = None
    position_type: str | None = None
    game_type: str | None = None
    source: str | None = None


class RawLogIngestRequest(BaseModel):
    store_id: str
    logs: list[RawLogIngestItem]


class IngestResult(BaseModel):
    inserted: int
    skipped: int
    analysis_ran: bool = False
    recommendations_created: int | None = None
    tier_counts: dict[str, int] | None = None


class AnalysisRunRequest(BaseModel):
    store_id: str
    target_date: date | None = None
    run_feedback: bool = True


class DailyLoopRequest(BaseModel):
    store_id: str


class DailyPredictionReportOut(BaseModel):
    store_id: str
    target_date: date | None = None
    report: dict


class PeriodStatisticsOut(BaseModel):
    store_id: str
    period: str
    data: dict


class DailyLearningCycleOut(BaseModel):
    store_id: str
    result: dict
