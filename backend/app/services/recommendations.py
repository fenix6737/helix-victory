import json
from datetime import date, datetime, timedelta, timezone

from app.timeutil import analysis_target_date, jst_today

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.cache import cache_delete_pattern, cache_get, cache_set
from app.config import settings
from app.featured import classify_featured
from app.game_type import classify_game_type, icon_variant
from app.models import Machine, RawLog, Recommendation, Store
from app.analysis.engine import infer_position
from app.analysis.investment_prediction_engine import predict_investment
from app.services.daily_hits import latest_logs_for_store_day, log_atari_fields
from app.schemas import MachineDetailOut, RecommendationItem, TimeSeriesPoint, TodayRecommendationsOut


async def list_stores(db: AsyncSession) -> list[Store]:
    result = await db.execute(select(Store).where(Store.is_active.is_(True)))
    return list(result.scalars().all())


async def get_today_recommendations(
    db: AsyncSession,
    store_id: str,
    target_date: date | None = None,
    game_type: str = "all",
) -> TodayRecommendationsOut | None:
    target = target_date or analysis_target_date()
    cache_key = f"ranking:{store_id}:{target.isoformat()}:{game_type}"

    async def _resolve_target() -> date:
        probe = await db.execute(
            select(Recommendation.target_date)
            .where(Recommendation.store_id == store_id)
            .order_by(Recommendation.target_date.desc())
            .limit(1)
        )
        latest = probe.scalar_one_or_none()
        if latest is None:
            return target
        has_target = await db.scalar(
            select(func.count(Recommendation.id)).where(
                Recommendation.store_id == store_id,
                Recommendation.target_date == target,
            )
        )
        if (has_target or 0) > 0:
            return target
        return latest

    target = await _resolve_target()
    cache_key = f"ranking:{store_id}:{target.isoformat()}:{game_type}"

    cached = await cache_get(cache_key)
    if cached:
        return TodayRecommendationsOut(**cached)

    store = await db.get(Store, store_id)
    if not store:
        return None

    stmt = (
        select(Recommendation)
        .where(Recommendation.store_id == store_id, Recommendation.target_date == target)
        .options(joinedload(Recommendation.machine))
        .order_by(Recommendation.rank)
    )
    result = await db.execute(stmt)
    recs = list(result.scalars().unique().all())

    machine_ids = [r.machine_id for r in recs]
    week_diffs = await _week_diff_totals(db, machine_ids)
    latest_day_logs = await latest_logs_for_store_day(db, store_id, target)

    def to_item(r: Recommendation, display_rank: int) -> RecommendationItem:
        reasons = json.loads(r.reasons) if r.reasons.startswith("[") else [r.reasons]
        m = r.machine
        gtype = getattr(m, "game_type", None) or classify_game_type(m.title)
        pos = m.position_type or infer_position(
            m.machine_number, m.island_id, store_id
        )
        inv = predict_investment(
            title=m.title,
            game_type=gtype,
            morning_score=r.score,
            waveform_ml_class=r.waveform or "",
            store_mode=r.store_mode,
        )
        feat, fgid, fbadge = classify_featured(m.title)
        bb, rb, atari = log_atari_fields(latest_day_logs.get(r.machine_id))
        spec_lines = _machine_spec_lines(m.title, gtype)
        spec_summary = _machine_spec_summary(m.title, gtype)
        return RecommendationItem(
            rank=display_rank,
            machine_id=r.machine_id,
            title=m.title,
            machine_number=m.machine_number,
            island_id=m.island_id,
            position_type=pos,
            week_diff_total=week_diffs.get(r.machine_id),
            is_featured=feat,
            featured_group=fgid,
            featured_badge=fbadge,
            spec_summary=spec_summary,
            spec_lines=spec_lines,
            score=round(r.score, 1),
            tier=r.tier or "recommend",
            reasons=reasons,
            sample_count=r.sample_count,
            period_days=r.period_days,
            confidence=round(r.confidence, 2),
            has_missing_data=r.has_missing_data,
            store_mode=r.store_mode,
            waveform=r.waveform,
            game_type=gtype,
            icon_variant=icon_variant(m.title, gtype),
            expected_investment=inv["expected_investment"],
            max_risk_line=inv["max_risk_line"],
            low_risk_zone=inv["low_risk_zone"],
            deep_hole_probability=inv["deep_hole_probability"],
            daily_big_count=bb,
            daily_reg_count=rb,
            daily_atari_total=atari,
        )

    all_recommend: list[RecommendationItem] = []
    all_hold: list[RecommendationItem] = []
    exclude_preview: list[RecommendationItem] = []
    store_mode: str | None = None

    for r in recs:
        if not store_mode and r.store_mode:
            store_mode = r.store_mode
        tier = r.tier or "recommend"
        if tier == "recommend":
            all_recommend.append(to_item(r, len(all_recommend) + 1))
        elif tier == "hold":
            all_hold.append(to_item(r, len(all_hold) + 1))
        elif tier == "exclude" and len(exclude_preview) < 30:
            exclude_preview.append(to_item(r, len(exclude_preview) + 1))

    def _filter(items: list[RecommendationItem]) -> list[RecommendationItem]:
        if game_type == "all":
            return items
        return [i for i in items if i.game_type == game_type]

    recommend = _finalize_list(_filter(all_recommend), 20)
    hold = _finalize_list(_filter(all_hold), 15)
    exclude_preview = _finalize_list(_filter(exclude_preview), 30)

    out = TodayRecommendationsOut(
        store_id=store_id,
        store_name=store.name,
        target_date=target,
        generated_at=datetime.now(timezone.utc),
        store_mode=store_mode,
        recommend=recommend,
        hold=hold,
        exclude_preview=exclude_preview,
        items=recommend,
        slot_recommend=sum(1 for i in all_recommend if i.game_type == "slot"),
        slot_hold=sum(1 for i in all_hold if i.game_type == "slot"),
        pachinko_recommend=sum(1 for i in all_recommend if i.game_type == "pachinko"),
        pachinko_hold=sum(1 for i in all_hold if i.game_type == "pachinko"),
    )
    await cache_set(cache_key, out.model_dump(), settings.cache_ttl_ranking)
    return out


def _finalize_list(items: list[RecommendationItem], limit: int) -> list[RecommendationItem]:
    """スコア順（rank）を維持したまま表示用連番のみ付け直す"""
    ordered = sorted(items, key=lambda x: x.rank)
    out: list[RecommendationItem] = []
    for i, item in enumerate(ordered[:limit], start=1):
        out.append(item.model_copy(update={"rank": i}))
    return out


async def _week_diff_totals(db: AsyncSession, machine_ids: list[int]) -> dict[int, int]:
    if not machine_ids:
        return {}
    since = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(RawLog.machine_id, func.sum(RawLog.diff_coins))
        .where(
            RawLog.machine_id.in_(machine_ids),
            RawLog.captured_at >= since,
            RawLog.diff_coins.isnot(None),
        )
        .group_by(RawLog.machine_id)
    )
    result = await db.execute(stmt)
    return {int(mid): int(total or 0) for mid, total in result.all()}


async def backfill_machine_game_types(db: AsyncSession, store_id: str) -> int:
    result = await db.execute(select(Machine).where(Machine.store_id == store_id))
    updated = 0
    for m in result.scalars().all():
        gt = classify_game_type(m.title)
        if m.game_type != gt:
            m.game_type = gt
            updated += 1
    await db.commit()
    await cache_delete_pattern(f"ranking:{store_id}:*")
    return updated


async def get_machine_detail(db: AsyncSession, machine_id: int) -> MachineDetailOut | None:
    cache_key = f"machine_stats:{machine_id}"
    cached = await cache_get(cache_key)
    if cached:
        return MachineDetailOut(**cached)

    machine = await db.get(Machine, machine_id)
    if not machine:
        return None

    gtype = machine.game_type or classify_game_type(machine.title)
    spec_lines = _machine_spec_lines(machine.title, gtype)

    store = await db.get(Store, machine.store_id)
    target = analysis_target_date()

    rec_stmt = select(Recommendation).where(
        Recommendation.machine_id == machine_id,
        Recommendation.target_date == target,
    )
    rec_result = await db.execute(rec_stmt)
    rec = rec_result.scalar_one_or_none()

    since = datetime.now(timezone.utc) - timedelta(days=7)
    log_stmt = (
        select(RawLog)
        .where(RawLog.machine_id == machine_id, RawLog.captured_at >= since)
        .order_by(RawLog.captured_at)
    )
    log_result = await db.execute(log_stmt)
    logs = list(log_result.scalars().all())

    time_series = [
        TimeSeriesPoint(
            captured_at=l.captured_at,
            diff_coins=l.diff_coins,
            rotation_count=l.rotation_count,
            big_count=l.big_count,
            reg_count=l.reg_count,
            final_games=l.final_games,
            is_operating=l.is_operating,
        )
        for l in logs
    ]

    reasons: list[str] = []
    score: float | None = None
    sample_count = 0
    period_days = 0
    confidence = 0.0
    has_missing = False

    tier: str | None = None
    store_mode: str | None = None
    waveform: str | None = None

    if rec:
        reasons = json.loads(rec.reasons) if rec.reasons.startswith("[") else [rec.reasons]
        score = round(rec.score, 1)
        sample_count = rec.sample_count
        period_days = rec.period_days
        confidence = round(rec.confidence, 2)
        has_missing = rec.has_missing_data
        tier = rec.tier
        store_mode = rec.store_mode
        waveform = rec.waveform

    sunk_days = _calc_sunk_days(logs)
    hold_trend = _calc_hold_trend(logs)
    island_hist = _island_summary(logs, machine.island_id, gtype)
    day_aff = _day_affinity_summary(logs)
    day_logs = await latest_logs_for_store_day(db, machine.store_id, target)
    bb, rb, atari = log_atari_fields(day_logs.get(machine.id))

    out = MachineDetailOut(
        machine_id=machine.id,
        store_id=machine.store_id,
        store_name=store.name if store else "",
        machine_number=machine.machine_number,
        title=machine.title,
        island_id=machine.island_id,
        position_type=machine.position_type,
        score=score,
        tier=tier,
        store_mode=store_mode,
        waveform=waveform,
        reasons=reasons,
        sample_count=sample_count,
        period_days=period_days,
        confidence=confidence,
        has_missing_data=has_missing,
        time_series=time_series,
        sunk_days=sunk_days,
        hold_trend=hold_trend,
        island_injection_history=island_hist,
        day_affinity=day_aff,
        game_type=gtype,
        spec_lines=spec_lines,
        daily_big_count=bb,
        daily_reg_count=rb,
        daily_atari_total=atari,
    )
    await cache_set(cache_key, out.model_dump(), settings.cache_ttl_stats)
    return out


def _machine_spec_lines(title: str, game_type: str) -> list[str]:
    import re

    lines: list[str] = []
    if game_type == "pachinko":
        for pat, label in [
            (r"1/\d{2,4}", "大当たり確率"),
            (r"\d{1,2}連", "連チャン"),
            (r"確変", "確変"),
            (r"電サポ", "電チュー寄り"),
            (r"羽根物", "羽根物"),
            (r"潜伏", "潜伏"),
        ]:
            m = re.search(pat, title)
            if m:
                lines.append(f"{label}: {m.group(0)}")
        if not lines:
            lines.append("機種名からスペック語句を抽出（詳細は店頭表記を確認）")
        lines.append(f"表示名: {title[:80]}")
    else:
        lines.append(f"機種: {title[:80]}")
        if re.search(r"AT|ART", title, re.I):
            lines.append("タイプ: AT/ART系")
        elif re.search(r"Aタイプ", title):
            lines.append("タイプ: Aタイプ")
        else:
            lines.append("タイプ: スマスロ/6.5号機等（名称参照）")
    return lines


def _machine_spec_summary(title: str, game_type: str) -> str:
    lines = _machine_spec_lines(title, game_type)
    if not lines:
        return ""
    parts = [x for x in lines[:2] if x]
    return " / ".join(parts)


def _calc_sunk_days(logs: list[RawLog]) -> int | None:
    if len(logs) < 2:
        return None
    daily: dict[date, int | None] = {}
    for l in logs:
        d = l.captured_at.date()
        if l.diff_coins is not None:
            daily[d] = l.diff_coins
    if not daily:
        return None
    sorted_days = sorted(daily.keys(), reverse=True)
    sunk = 0
    for d in sorted_days:
        v = daily[d]
        if v is not None and v < 0:
            sunk += 1
        else:
            break
    return sunk if sunk > 0 else None


def _island_summary(
    logs: list[RawLog], island_id: str | None, game_type: str = "slot"
) -> str | None:
    if not island_id:
        return None
    same = [l for l in logs if l.diff_coins is not None]
    if len(same) < 2:
        return None
    avg = sum(l.diff_coins for l in same if l.diff_coins is not None) / len(same)
    unit = "玉" if game_type == "pachinko" else "枚"
    return f"島{island_id} 直近平均 {int(avg):+d}{unit}"


def _day_affinity_summary(logs: list[RawLog]) -> str | None:
    if len(logs) < 5:
        return None
    from collections import defaultdict

    by_wd: dict[int, list[int]] = defaultdict(list)
    for l in logs:
        if l.diff_coins is not None:
            by_wd[l.captured_at.weekday()].append(l.diff_coins)
    if not by_wd:
        return None
    best = max(by_wd.items(), key=lambda x: sum(x[1]) / len(x[1]))
    names = ["月", "火", "水", "木", "金", "土", "日"]
    return f"{names[best[0]]}曜の相性が良好"


def _calc_hold_trend(logs: list[RawLog]) -> str | None:
    if len(logs) < 3:
        return None
    diffs = [l.diff_coins for l in logs if l.diff_coins is not None]
    if len(diffs) < 3:
        return None
    span = max(diffs) - min(diffs)
    if span <= 500:
        return "据え置き傾向"
    return None
