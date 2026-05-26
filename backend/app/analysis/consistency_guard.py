"""整合性監査 v3.5 — API/UI/推奨の一貫性（integrity_guard 拡張）"""

from __future__ import annotations

from datetime import datetime, timezone

from app.analysis.integrity_guardian import audit_data_integrity
import pandas as pd


def audit_consistency(
    *,
    df: pd.DataFrame,
    store_id: str,
    live_ev_payload: dict | None = None,
    recommendations_count: int = 0,
    api_healthy: bool = True,
) -> dict:
    integrity = audit_data_integrity(df, store_id)
    if df.empty:
        integrity = {**integrity, "allow_analysis": True, "ok": True, "severity": "ok", "issues": []}
    issues = list(integrity.get("issues", []))
    block_recommendations = not integrity.get("allow_analysis", True)
    block_analysis = not integrity.get("allow_analysis", True) and not df.empty
    ui_warning: str | None = None

    if not api_healthy:
        issues.append("API unhealthy")
        ui_warning = "API接続異常 — キャッシュ表示"
        block_analysis = True

    if live_ev_payload is not None:
        if live_ev_payload.get("combat_mode") is None:
            issues.append("null combat_mode")
            ui_warning = ui_warning or "実戦モード未取得"
        prim = live_ev_payload.get("primary")
        alts = live_ev_payload.get("alternatives") or []
        if live_ev_payload.get("should_play") and not prim and not alts:
            issues.append("推奨未表示")
            block_recommendations = True
        for field in (
            "collapse_probability",
            "island_state",
            "retreat_reason",
            "death_line",
        ):
            if field not in live_ev_payload:
                issues.append(f"live-ev missing {field}")

        rec_s = live_ev_payload.get("recommend_score", 0)
        ret_s = live_ev_payload.get("retreat_score", 0)
        if prim and rec_s + 5 < ret_s and live_ev_payload.get("should_play"):
            issues.append("score mismatch: retreat>recommend while should_play")
            block_recommendations = True

        if live_ev_payload.get("fake_release") and live_ev_payload.get("should_play"):
            issues.append("fake_release推奨禁止")
            block_recommendations = True

        if live_ev_payload.get("island_state") == "collapse" and live_ev_payload.get("should_play"):
            issues.append("崩壊島推奨禁止")
            block_recommendations = True

    if recommendations_count == 0 and integrity.get("allow_analysis") and df is not None and not df.empty:
        issues.append("空データ推奨の疑い")

    severity = integrity.get("severity", "ok")
    if issues and severity == "ok":
        severity = "warning"
    if block_recommendations or block_analysis:
        severity = "critical"

    return {
        "ok": len(issues) == 0,
        "severity": severity,
        "issues": issues,
        "allow_analysis": integrity.get("allow_analysis", False) and not block_analysis,
        "allow_recommendations": not block_recommendations,
        "block_ui_recommendations": block_recommendations,
        "ui_warning": ui_warning,
        "integrity": integrity,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "store_id": store_id,
    }
