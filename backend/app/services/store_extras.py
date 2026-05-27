"""店舗付加情報 — 収集健康・トレンド・島ヒートマップ・イベント日"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.island import compute_island_stats, enrich_island_column
from app.models import RawLog, StoreDailyInsight, StoreMetadata, Recommendation
from app.timeutil import analysis_target_date


def _build_collector_health(
    store_id: str,
    sources: dict[str, int],
    warnings: list[str],
) -> dict:
    total = sum(sources.values())
    labels = {
        "daidata": "Site777（daidata）",
        "anaslo": "アナスロ",
        "minrepo": "みんレポ",
        "minrepo_pachinko": "みんレポ（パチ）",
        "kicona_multi": "キコーナ複合",
    }
    active = [labels.get(k, k) for k, v in sources.items() if v > 0]
    has_daidata = sources.get("daidata", 0) > 0

    status = "ok"
    message = "データ収集は正常です"
    level = "ok"

    if total == 0:
        status = "empty"
        level = "error"
        message = "24時間以内の収集データがありません"
    elif store_id == "maruhan_umeda" and not has_daidata:
        status = "degraded"
        level = "warn"
        parts = "・".join(active) if active else "補助ソースのみ"
        message = f"Site777未連携 — {parts}で分析中"
        if warnings:
            message += f"（{warnings[0][:40]}）"
    elif warnings:
        status = "degraded"
        level = "warn"
        message = warnings[0][:120]

    return {
        "status": status,
        "level": level,
        "message": message,
        "sources_24h": sources,
        "active_sources": active,
        "daidata_connected": has_daidata,
    }


async def _sources_24h(db: AsyncSession, store_id: str) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = await db.execute(
        select(RawLog.source, func.count(RawLog.id))
        .where(RawLog.store_id == store_id, RawLog.captured_at >= since)
        .group_by(RawLog.source)
    )
    return {str(src or "unknown"): int(cnt) for src, cnt in rows.all()}


async def get_insight_trend(db: AsyncSession, store_id: str) -> dict:
    target = analysis_target_date()
    today_row = await db.get(StoreDailyInsight, (store_id, target))
    prev_row = await db.get(StoreDailyInsight, (store_id, target - timedelta(days=1)))

    if not today_row:
        return {
            "posture": "unknown",
            "posture_label": "データ準備中",
            "summary": "分析が完了すると、今日の攻め方が表示されます",
            "danger_score": None,
            "score_delta": None,
            "should_play": None,
        }

    score = float(today_row.danger_score or 0)
    prev_score = float(prev_row.danger_score) if prev_row else score
    delta = round(score - prev_score, 1)

    if not today_row.should_play or today_row.danger_level in ("danger", "critical"):
        posture, label = "avoid", "今日は控えめ"
        summary = "危険度が高い — 打つなら厳選台のみ、無理はしない"
    elif today_row.danger_level == "caution" or score < 45:
        posture, label = "careful", "厳選で攻める"
        summary = "全体は様子見寄り — 推奨の上位だけに絞る"
    else:
        posture, label = "attack", "攻めてよい"
        summary = "店の状態は良好 — 推奨台を中心に打てる"

    if delta <= -8:
        summary += "（前日より店の危険度は下がっています）"
    elif delta >= 8:
        summary += "（前日より店の危険度は上がっています）"

    store_mode = None
    rec_mode = await db.scalar(
        select(Recommendation.store_mode)
        .where(
            Recommendation.store_id == store_id,
            Recommendation.target_date == target,
            Recommendation.store_mode.isnot(None),
        )
        .limit(1)
    )
    store_mode = rec_mode

    return {
        "posture": posture,
        "posture_label": label,
        "summary": summary,
        "danger_score": score,
        "score_delta": delta,
        "should_play": today_row.should_play,
        "headline": today_row.headline,
        "store_mode": store_mode,
    }


async def get_island_heatmap(db: AsyncSession, store_id: str) -> list[dict]:
    target = analysis_target_date()
    since = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(
            RawLog.machine_id,
            RawLog.machine_number,
            RawLog.captured_at,
            RawLog.diff_coins,
            RawLog.is_operating,
            RawLog.rotation_count,
        )
        .where(RawLog.store_id == store_id, RawLog.captured_at >= since)
    )
    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return []

    df = pd.DataFrame(
        rows,
        columns=[
            "machine_id",
            "machine_number",
            "captured_at",
            "diff_coins",
            "is_operating",
            "rotation_count",
        ],
    )
    df = enrich_island_column(df, store_id)
    stats = compute_island_stats(df, target)
    if stats.empty:
        return []

    cells = []
    for _, r in stats.iterrows():
        mean_diff = float(r.get("island_mean_diff") or 0)
        ops = float(r.get("island_ops_rate") or 0)
        temp = "hot" if mean_diff > 300 else "cold" if mean_diff < -300 else "neutral"
        cells.append(
            {
                "island_id": str(r["island_id"]),
                "machine_count": int(r.get("island_machine_count") or 0),
                "mean_diff": int(mean_diff),
                "ops_rate": round(ops, 2),
                "temperature": temp,
                "label": _island_label(str(r["island_id"])),
            }
        )
    cells.sort(key=lambda x: x["mean_diff"], reverse=True)
    return cells[:24]


def _island_label(island_id: str) -> str:
    if island_id.startswith("island_"):
        block = island_id.replace("island_", "")
        return f"{block}番台ブロック"
    return island_id


async def get_event_calendar(db: AsyncSession, store_id: str) -> dict:
    target = analysis_target_date()
    meta_row = await db.get(StoreMetadata, store_id)
    meta = json.loads(meta_row.metadata_json) if meta_row else {}
    event_days: list[int] = meta.get("event_days") or [3, 9]

    mode_labels = {
        "recovery": "回収モード",
        "normal": "通常",
        "release": "放出モード",
        "event": "イベント日",
    }
    insight = await db.get(StoreDailyInsight, (store_id, target))
    store_mode = insight and json.loads(insight.feature_audit_json or "{}").get("store_mode")
    if not store_mode:
        rec = await db.scalar(
            select(Recommendation.store_mode).where(
                Recommendation.store_id == store_id,
                Recommendation.target_date == target,
            ).limit(1)
        )
        store_mode = rec

    month_start = target.replace(day=1)
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    month_end = next_month - timedelta(days=1)

    start = month_start - timedelta(days=7)
    end = month_end + timedelta(days=7)

    insight_rows = (
        await db.execute(
            select(StoreDailyInsight).where(
                StoreDailyInsight.store_id == store_id,
                StoreDailyInsight.target_date >= start,
                StoreDailyInsight.target_date <= end,
            )
        )
    ).scalars().all()
    insight_map = {r.target_date: r for r in insight_rows}

    rec_rows = await db.execute(
        select(
            Recommendation.target_date,
            func.sum(case((Recommendation.tier == "recommend", 1), else_=0)).label(
                "rec_count"
            ),
        )
        .where(
            Recommendation.store_id == store_id,
            Recommendation.target_date >= start,
            Recommendation.target_date <= end,
        )
        .group_by(Recommendation.target_date)
    )
    rec_map = {d: int(c or 0) for d, c in rec_rows.all()}

    def day_expectancy(d: date, is_event: bool) -> tuple[str, int, str]:
        score = 50
        insight_d = insight_map.get(d)
        rec_cnt = rec_map.get(d, 0)
        if insight_d:
            danger = float(insight_d.danger_score or 50)
            score += int((50 - danger) * 0.7)
            score += 10 if bool(insight_d.should_play) else -8
        if rec_cnt:
            score += min(12, rec_cnt // 2)
        if is_event:
            score += 8
        score = max(0, min(100, score))
        if score >= 72:
            return "hot", score, "激熱"
        if score >= 58:
            return "high", score, "高期待"
        if score <= 38:
            return "low", score, "低期待"
        return "neutral", score, "様子見"

    days = []
    d = month_start
    while d <= month_end:
        dom = d.day
        is_event = dom in event_days or (dom % 10) in event_days
        level, score, label = day_expectancy(d, is_event)
        days.append(
            {
                "date": d.isoformat(),
                "day": dom,
                "weekday": d.weekday(),
                "is_event_day": is_event,
                "is_target": d == target,
                "expectancy_level": level,
                "expectancy_score": score,
                "label": label,
            }
        )
        d += timedelta(days=1)

    return {
        "target_date": target.isoformat(),
        "event_days": event_days,
        "store_mode": store_mode,
        "store_mode_label": mode_labels.get(str(store_mode or ""), "分析中"),
        "days": days,
    }


async def get_store_extras(db: AsyncSession, store_id: str) -> dict:
    sources = await _sources_24h(db, store_id)
    meta_row = await db.get(StoreMetadata, store_id)
    meta = json.loads(meta_row.metadata_json) if meta_row else {}
    warnings: list[str] = meta.get("collector_warnings") or []

    return {
        "store_id": store_id,
        "collector": _build_collector_health(store_id, sources, warnings),
        "trend": await get_insight_trend(db, store_id),
        "islands": await get_island_heatmap(db, store_id),
        "events": await get_event_calendar(db, store_id),
    }
