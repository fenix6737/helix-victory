"""リアルタイム期待値 — 統合サービス"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.analysis.alternative_engine import find_alternatives
from app.analysis.combat_mode_engine import resolve_combat_mode
from app.analysis.current_ev_engine import compute_current_ev
from app.analysis.dual_score_engine import compute_dual_scores
from app.analysis.investment_prediction_engine import predict_investment
from app.analysis.island_collapse_engine import detect_island_collapse, primary_island_collapsed
from app.analysis.danger_ml import score_danger_ml
from app.analysis.drift_detection import detect_feature_drift
from app.analysis.retreat_engine import apply_retreat_to_candidates, evaluate_retreat
from app.analysis.engine import classify_waveform
from app.analysis.island_live_engine import compute_island_live
from app.analysis.island import enrich_island_column
from app.analysis.seat_status_engine import infer_seat_status, seat_status_label
from app.analysis.quantile_ev_engine import compute_quantile_ev
from app.analysis.waveform_ml import analyze_waveform_series
from app.cache import cache_get as _cache_get_simple
from app.cache import cache_get_with_meta, cache_set, is_cache_degraded
from app.analysis.consistency_guard import audit_consistency
from app.config import settings
from app.game_type import classify_game_type, icon_variant
from app.models import Machine, RawLog, Recommendation, Store, StoreDailyInsight, StoreMetadata
from app.schemas import LiveEvMachineOut, StoreLiveEvOut
from app.timeutil import analysis_target_date, jst_now


async def get_store_live_ev(
    db: AsyncSession,
    store_id: str,
    game_type: str = "all",
    target_date: date | None = None,
) -> StoreLiveEvOut | None:
    target = target_date or analysis_target_date()
    cache_key = f"live_ev:{store_id}:{target.isoformat()}:{game_type}"
    cached, cache_meta = await cache_get_with_meta(cache_key)
    if cached:
        out = StoreLiveEvOut(**cached)
        if cache_meta.get("stale") or cache_meta.get("degraded"):
            return out.model_copy(
                update={
                    "stale_warning": True,
                    "cache_degraded": cache_meta.get("degraded", False),
                }
            )
        return out

    store = await db.get(Store, store_id)
    if not store:
        return None

    since_recent = jst_now().astimezone(timezone.utc) - timedelta(hours=12)
    since_hist = jst_now().astimezone(timezone.utc) - timedelta(days=30)

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
        .where(RawLog.store_id == store_id, RawLog.captured_at >= since_hist)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return None

    df = pd.DataFrame(
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
    df = enrich_island_column(df, store_id)
    recent_df = df[pd.to_datetime(df["captured_at"], utc=True) >= since_recent]
    hist_df = df[pd.to_datetime(df["captured_at"], utc=True) < since_recent]

    meta_row = await db.get(StoreMetadata, store_id)
    meta = json.loads(meta_row.metadata_json) if meta_row else {}
    event_days = meta.get("event_days") or [3, 9]

    insight_row = await db.get(StoreDailyInsight, (store_id, target))
    prior_audit = json.loads(insight_row.feature_audit_json) if insight_row else {}

    drift = detect_feature_drift(hist_df, recent_df, prior_audit)
    islands = compute_island_live(df)
    collapse_info = detect_island_collapse(islands, df)
    danger = score_danger_ml(
        df, target, event_days, drift_score=float(drift.get("drift_score", 0))
    )

    fake_release_rate = 0.0
    ops_drop_rate = 0.0
    if not recent_df.empty and recent_df["is_operating"].notna().any():
        ops_drop_rate = max(0.0, float(hist_df["is_operating"].mean()) - float(recent_df["is_operating"].mean())) if not hist_df.empty else 0.0

    rec_stmt = (
        select(Recommendation)
        .where(
            Recommendation.store_id == store_id,
            Recommendation.target_date == target,
            Recommendation.tier.in_(["recommend", "hold"]),
        )
        .options(joinedload(Recommendation.machine))
        .order_by(Recommendation.rank)
    )
    recs = list((await db.execute(rec_stmt)).scalars().unique().all())

    enriched: list[dict] = []
    for rec in recs:
        gtype = getattr(rec.machine, "game_type", None) or classify_game_type(rec.machine.title)
        if game_type != "all" and gtype != game_type:
            continue

        g = df[df["machine_id"] == rec.machine_id]
        if g.empty:
            continue

        g_recent = g[pd.to_datetime(g["captured_at"], utc=True) >= since_recent]
        work = g_recent if not g_recent.empty else g.tail(12)

        latest = work.iloc[-1]
        diffs = work["diff_coins"].tolist()
        rule_wf = classify_waveform(work.sort_values("captured_at")).value
        wf = analyze_waveform_series(diffs, rule_wf)
        if wf.get("fake_release"):
            fake_release_rate = min(1.0, fake_release_rate + 0.08)

        rot = work["rotation_count"].dropna()
        rot_vel = float(rot.diff().mean()) if len(rot) >= 2 else 0.0
        peak = float(work["diff_coins"].max()) if work["diff_coins"].notna().any() else None

        island_id = str(latest.get("island_id") or "")
        isl = islands.get(island_id, {})
        island_ops = isl.get("ops_rate", 0.5)
        island_state = isl.get("state", "neutral")

        seat = infer_seat_status(work)
        ev = compute_current_ev(
            machine_id=rec.machine_id,
            morning_score=rec.score,
            title=rec.machine.title,
            game_type=gtype,
            current_diff=int(latest["diff_coins"]) if pd.notna(latest.get("diff_coins")) else None,
            peak_diff=int(peak) if peak is not None else None,
            rotation_velocity=rot_vel,
            island_ops_rate=float(island_ops),
            waveform_ml_class=wf["ml_class"],
            seat_status=seat,
            store_mode=danger.store_mode,
            island_state=island_state,
        )
        dual = compute_dual_scores(
            morning_score=ev.morning_score,
            current_ev=ev.current_ev,
            exhaustion_rate=ev.exhaustion_rate,
            waveform_ml_class=wf["ml_class"],
            island_state=island_state,
            seat_status=seat.value,
            island_ops_rate=float(island_ops),
            drift_score=float(drift.get("drift_score", 0)),
            collapse_probability=float(collapse_info.get("collapse_rate", 0)),
        )

        if wf.get("trap_penalty"):
            dual["recommend_score"] = max(0, dual["recommend_score"] - 15)
            dual["retreat_score"] = min(100, dual["retreat_score"] + 20)
            ev.playable = False

        inv = predict_investment(
            title=rec.machine.title,
            game_type=gtype,
            morning_score=ev.morning_score,
            rotation_velocity=rot_vel,
            waveform_ml_class=wf["ml_class"],
            island_state=island_state,
            seat_status=seat.value,
            store_mode=danger.store_mode,
            exhaustion_rate=ev.exhaustion_rate,
            collapse_probability=float(collapse_info.get("collapse_rate", 0)),
            retreat_score=dual["retreat_score"],
        )

        quantile = compute_quantile_ev(
            work,
            ev.morning_score,
            fake_release_rate=fake_release_rate,
            island_collapse_rate=float(collapse_info.get("collapse_rate", 0)),
            drift_score=float(drift.get("drift_score", 0)),
            ops_drop_rate=ops_drop_rate,
        )

        enriched.append(
            {
                "machine_id": rec.machine_id,
                "machine_number": rec.machine.machine_number,
                "title": rec.machine.title,
                "game_type": gtype,
                "icon_variant": icon_variant(rec.machine.title, gtype),
                "island_id": island_id or None,
                "morning_score": ev.morning_score,
                "current_ev": ev.current_ev,
                "exhaustion_rate": ev.exhaustion_rate,
                "ev_delta": ev.ev_delta,
                "playable": ev.playable,
                "seat_status": seat.value,
                "seat_label": seat_status_label(seat),
                "waveform_ml_class": wf["ml_class"],
                "is_setting_wave": wf["is_setting_like"],
                "reasons": ev.reasons,
                "tier": rec.tier,
                "quantile": quantile,
                "investment": inv,
                "recommend_score": dual["recommend_score"],
                "retreat_score": dual["retreat_score"],
                "hit_confidence": dual["hit_confidence"],
                "fake_release": bool(wf.get("fake_release")),
                "trap_wave": wf["ml_class"] == "trap_wave",
                "watched": seat.value == "watched",
            }
        )

    playable_sorted = sorted(
        [e for e in enriched if e["playable"] and e.get("retreat_score", 0) < 55],
        key=lambda x: (x.get("recommend_score", x["current_ev"]), x["current_ev"]),
        reverse=True,
    )
    all_sorted = sorted(
        enriched,
        key=lambda x: (x.get("recommend_score", x["current_ev"]), x["current_ev"]),
        reverse=True,
    )

    primary = playable_sorted[0] if playable_sorted else (all_sorted[0] if all_sorted else None)
    candidate_pool = playable_sorted or all_sorted
    alts = find_alternatives(primary or {}, candidate_pool, df, limit=2, islands=islands)

    collapse_prob = float(
        (primary or {}).get("quantile", {}).get("collapse_probability", 0)
        or collapse_info.get("collapse_rate", 0)
    )
    island_collapsed = primary_island_collapsed(primary, collapse_info)

    retreat = evaluate_retreat(
        primary=primary,
        candidates=candidate_pool,
        df=df,
        islands=islands,
        drift=drift,
        danger_level=danger.level.value,
        danger_score=danger.score,
        island_collapsed=island_collapsed,
        collapse_probability=collapse_prob,
        investment=(primary or {}).get("investment"),
    )

    old_primary = primary
    primary, alts_rest, dropped_primary = apply_retreat_to_candidates(
        primary, candidate_pool, retreat
    )
    if not primary and all_sorted:
        primary = all_sorted[0]
        retreat.reasons.append("フォールバック候補")

    if primary and dropped_primary and primary.get("machine_id") != dropped_primary.get("machine_id"):
        alts = find_alternatives(primary, candidate_pool, df, limit=2, islands=islands)
    elif alts_rest:
        alts = [
            {
                "rank": i + 2,
                "machine_id": c.get("machine_id"),
                "machine_number": c.get("machine_number"),
                "title": c.get("title"),
                "current_ev": c.get("current_ev"),
                "seat_status": c.get("seat_status"),
                "island_id": c.get("island_id"),
                "reason": "撤退後候補",
            }
            for i, c in enumerate(alts_rest[:2])
        ]

    primary_out = None
    if primary:
        primary_out = LiveEvMachineOut(
            rank=1,
            machine_id=primary["machine_id"],
            machine_number=primary["machine_number"],
            title=primary["title"],
            game_type=primary["game_type"],
            icon_variant=primary["icon_variant"],
            morning_score=primary["morning_score"],
            current_ev=primary["current_ev"],
            exhaustion_rate=primary["exhaustion_rate"],
            ev_delta=primary["ev_delta"],
            playable=primary["playable"],
            seat_status=primary["seat_status"],
            seat_label=primary["seat_label"],
            waveform_ml_class=primary["waveform_ml_class"],
            island_id=primary.get("island_id"),
            reasons=primary["reasons"],
            expected_investment=primary.get("investment", {}).get("expected_investment"),
            max_risk_line=primary.get("investment", {}).get("max_risk_line"),
            deep_hole_probability=primary.get("investment", {}).get("deep_hole_probability"),
        )

    alt_out = [
        LiveEvMachineOut(
            rank=a["rank"],
            machine_id=a["machine_id"],
            machine_number=a["machine_number"],
            title=a["title"],
            game_type=primary["game_type"] if primary else "slot",
            icon_variant=icon_variant(a["title"], primary["game_type"] if primary else "slot"),
            morning_score=0,
            current_ev=float(a.get("current_ev") or 0),
            exhaustion_rate=0,
            ev_delta=0,
            playable=True,
            seat_status=a.get("seat_status", "playing"),
            seat_label=a.get("seat_status", ""),
            waveform_ml_class="",
            island_id=a.get("island_id"),
            reasons=[a.get("reason", "第二候補")],
        )
        for a in alts
    ]

    hot_islands = [
        v
        for v in islands.values()
        if v.get("state") in ("heating", "active") or v.get("temperature") == "hot"
    ][:5]

    combat_cached = await _cache_get_simple(f"combat_status:{store_id}:{target.isoformat()}")
    manager_warning = (
        combat_cached.get("manager_shift", {}).get("ui_warning") if combat_cached else None
    )

    quantile_primary = primary.get("quantile", {}) if primary else {}
    inv_p = primary.get("investment", {}) if primary else {}
    deep_risk = bool(
        primary
        and (
            primary.get("exhaustion_rate", 0) > 0.72
            or inv_p.get("deep_hole_probability", 0) > 0.45
        )
    )

    force_no_play = danger.level.value == "critical" or retreat.should_retreat
    should_play_final = (
        not force_no_play
        and danger.should_play
        and retreat.should_play
        and primary is not None
    )

    combat_mode = resolve_combat_mode(
        danger_level=danger.level.value,
        danger_score=danger.score,
        should_play=should_play_final,
        integrity_ok=True,
        anomaly_block=False,
        manager_shift_prob=float(
            (combat_cached or {}).get("manager_shift", {}).get("operation_change_probability", 0)
        ),
        playable_count=len(playable_sorted) if playable_sorted else len(candidate_pool),
        store_mode=danger.store_mode,
        drift_score=float(drift.get("drift_score", 0)),
        force_retreat=retreat.should_retreat or island_collapsed,
        retreat_reasons=retreat.reasons,
    ).to_dict()

    confidence = max(
        0.2,
        1.0
        - float(drift.get("ev_confidence_penalty", 0))
        - collapse_prob * 0.3
        - (primary or {}).get("retreat_score", 0) / 200.0,
    )

    out = StoreLiveEvOut(
        store_id=store_id,
        store_name=store.name,
        target_date=target,
        generated_at=datetime.now(timezone.utc),
        should_play=should_play_final,
        danger_level=danger.level.value,
        danger_score=danger.score,
        danger_headline=danger.headline,
        danger_reasons=danger.reasons,
        drift_alerts=drift.get("alerts", []),
        primary=primary_out,
        alternatives=alt_out,
        playable_count=len(playable_sorted),
        ranked_preview=[
            LiveEvMachineOut(
                rank=i + 1,
                machine_id=e["machine_id"],
                machine_number=e["machine_number"],
                title=e["title"],
                game_type=e["game_type"],
                icon_variant=e["icon_variant"],
                morning_score=e["morning_score"],
                current_ev=e["current_ev"],
                exhaustion_rate=e["exhaustion_rate"],
                ev_delta=e["ev_delta"],
                playable=e["playable"],
                seat_status=e["seat_status"],
                seat_label=e["seat_label"],
                waveform_ml_class=e["waveform_ml_class"],
                island_id=e.get("island_id"),
                reasons=e["reasons"],
            )
            for i, e in enumerate((playable_sorted or all_sorted)[:5])
        ],
        hot_islands=hot_islands,
        islands_live=list(islands.values())[:12],
        quantile=quantile_primary,
        combat_mode=combat_mode,
        manager_warning=manager_warning,
        deep_risk=deep_risk,
        recommend_score=float((primary or {}).get("recommend_score", 0)),
        retreat_score=float((primary or {}).get("retreat_score", 0)),
        collapse_probability=float(quantile_primary.get("collapse_probability", collapse_prob)),
        island_state=str(
            islands.get(str((primary or {}).get("island_id") or ""), {}).get("state", "neutral")
        ),
        retreat_reason=retreat.reasons,
        death_line=float(inv_p.get("death_line", 0)),
        expected_investment=float(inv_p.get("expected_investment", 0)),
        fake_release=bool((primary or {}).get("fake_release")),
        trap_wave=bool((primary or {}).get("trap_wave")),
        watched=bool((primary or {}).get("watched")),
        confidence=round(confidence, 2),
        data_freshness_sec=45,
        stale_warning=is_cache_degraded(),
        cache_degraded=is_cache_degraded(),
        recent_drift=float(drift.get("drift_score", 0)),
        deep_harami=bool(inv_p.get("deep_harami_alert") or deep_risk),
        median_ev=float(quantile_primary.get("median_ev", 0)) or None,
        downside_ev=float(quantile_primary.get("downside_ev", 0)) or None,
        worst_case_ev=float(quantile_primary.get("worst_case_ev", 0)) or None,
    )

    consistency = audit_consistency(
        df=df,
        store_id=store_id,
        live_ev_payload=out.model_dump(),
        recommendations_count=len(playable_sorted),
    )
    if not consistency.get("allow_recommendations"):
        out = out.model_copy(update={"should_play": False})
        if consistency.get("ui_warning"):
            out = out.model_copy(
                update={
                    "manager_warning": consistency["ui_warning"],
                    "combat_mode": resolve_combat_mode(
                        danger_level=danger.level.value,
                        danger_score=danger.score,
                        should_play=False,
                        integrity_ok=True,
                        anomaly_block=True,
                        manager_shift_prob=0,
                        playable_count=0,
                        force_retreat=True,
                        retreat_reasons=consistency.get("issues", []),
                    ).to_dict(),
                }
            )

    payload = out.model_dump()
    await cache_set(cache_key, payload)
    await cache_set(f"retreat:{store_id}:{target.isoformat()}", retreat.to_dict())
    await cache_set(f"quantile:{store_id}:{target.isoformat()}", quantile_primary)
    await cache_set(f"island_state:{store_id}:{target.isoformat()}", list(islands.values())[:12])
    return out
