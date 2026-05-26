from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    machines: Mapped[list["Machine"]] = relationship(back_populates="store")
    raw_logs: Mapped[list["RawLog"]] = relationship(back_populates="store")
    store_meta: Mapped["StoreMetadata | None"] = relationship(back_populates="store", uselist=False)


class StoreMetadata(Base):
    """みんパチ等から取得した店舗メタ（旧イベント日・台数）"""

    __tablename__ = "store_metadata"

    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), primary_key=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    store: Mapped["Store"] = relationship(back_populates="store_meta")


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (UniqueConstraint("store_id", "machine_number", name="uq_store_machine_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    machine_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    game_type: Mapped[str] = mapped_column(String(16), default="slot", index=True)
    island_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    store: Mapped["Store"] = relationship(back_populates="machines")
    raw_logs: Mapped[list["RawLog"]] = relationship(back_populates="machine")


class RawLog(Base):
    __tablename__ = "raw_logs"
    __table_args__ = (
        Index("ix_raw_logs_store_machine_captured", "store_id", "machine_id", "captured_at"),
        Index("ix_raw_logs_captured_at", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey("machines.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    machine_number: Mapped[int] = mapped_column(Integer, nullable=False)
    diff_coins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rotation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    big_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reg_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    graph_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_operating: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="collector")

    store: Mapped["Store"] = relationship(back_populates="raw_logs")
    machine: Mapped["Machine"] = relationship(back_populates="raw_logs")


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("store_id", "target_date", "machine_id", name="uq_rec_store_date_machine"),
        Index("ix_recommendations_store_date_tier", "store_id", "target_date", "tier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey("machines.id"), index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    tier: Mapped[str] = mapped_column(String(16), default="recommend")
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reasons: Mapped[str] = mapped_column(Text, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    period_days: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    has_missing_data: Mapped[bool] = mapped_column(Boolean, default=False)
    store_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    waveform: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str] = mapped_column(String(32), default="engine_v2")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    machine: Mapped["Machine"] = relationship()


class StoreDailyInsight(Base):
    __tablename__ = "store_daily_insights"

    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), primary_key=True)
    target_date: Mapped[date] = mapped_column(Date, primary_key=True)
    danger_level: Mapped[str] = mapped_column(String(16), default="safe")
    danger_score: Mapped[float] = mapped_column(Float, default=0.0)
    should_play: Mapped[bool] = mapped_column(Boolean, default=True)
    headline: Mapped[str] = mapped_column(String(256), default="")
    danger_reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    feature_audit_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        Index("ix_outcomes_store_eval", "store_id", "eval_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    machine_id: Mapped[int] = mapped_column(Integer, ForeignKey("machines.id"), index=True)
    pred_date: Mapped[date] = mapped_column(Date, nullable=False)
    eval_date: Mapped[date] = mapped_column(Date, nullable=False)
    predicted_score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    actual_diff_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AnalysisWeights(Base):
    __tablename__ = "analysis_weights"

    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), primary_key=True)
    weights_json: Mapped[str] = mapped_column(Text, nullable=False)
    hit_rate_14d: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DailyPredictionReport(Base):
    """毎日の大当たり予測レポート（深夜バッチで保存）"""

    __tablename__ = "daily_prediction_reports"
    __table_args__ = (
        UniqueConstraint("store_id", "target_date", name="uq_daily_report_store_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    hit_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MachineBorder(Base):
    """機種別等価ボーダー（1,000円あたりの合格回転数）"""

    __tablename__ = "m_machine_borders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title_pattern: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    border_per_1000_yen: Mapped[float] = mapped_column(Float, nullable=False)
    game_type: Mapped[str] = mapped_column(String(16), default="pachinko")
    coin_price_yen: Mapped[float] = mapped_column(Float, default=4.0)
    base_games: Mapped[int] = mapped_column(Integer, default=400)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class StoreAnalysisSettings(Base):
    """店舗別 — 期待値モード（オカルト排除）トグル"""

    __tablename__ = "store_analysis_settings"

    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), primary_key=True)
    ev_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PlayRecord(Base):
    """ユーザー自身のプレイ記録（自己検証用）"""

    __tablename__ = "play_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(String(32), ForeignKey("stores.id"), index=True)
    machine_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("machines.id"), nullable=True)
    machine_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(128), default="")
    game_type: Mapped[str] = mapped_column(String(16), default="slot")
    invest_yen: Mapped[int] = mapped_column(Integer, default=0)
    result_yen: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(256), default="")
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
