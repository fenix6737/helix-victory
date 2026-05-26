"""データ整合性監査 — 壊れたデータで学習・推奨しない"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.timeutil import JST, jst_now


class IntegrityError(Exception):
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def audit_data_integrity(
    df: pd.DataFrame,
    store_id: str,
) -> dict:
    issues: list[str] = []
    severity = "ok"
    allow_analysis = True

    if df.empty:
        return {
            "ok": False,
            "severity": "critical",
            "allow_analysis": False,
            "issues": ["収集データ0件"],
        }

    required = {"machine_id", "machine_number", "captured_at", "diff_coins"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        issues.append(f"必須列欠損: {missing_cols}")
        allow_analysis = False
        severity = "critical"

    if "machine_number" in df.columns:
        dup = df.groupby(["machine_id", "captured_at"]).size()
        if (dup > 1).any():
            n = int((dup > 1).sum())
            issues.append(f"台×時刻の重複 {n}件")

    if "game_type" in df.columns:
        bad = df[~df["game_type"].isin(["slot", "pachinko"])]
        if len(bad) > 0:
            issues.append(f"game_type不正 {len(bad)}件")

    if "captured_at" in df.columns:
        ts = pd.to_datetime(df["captured_at"], utc=True)
        now = jst_now()
        future = ts > now + timedelta(hours=2)
        if future.any():
            issues.append(f"未来日時ログ {int(future.sum())}件")
        old = ts < now - timedelta(days=400)
        if old.any() and old.sum() > len(df) * 0.5:
            issues.append("ログが古すぎる（400日超過が過半）")

    miss_rate = float(df["diff_coins"].isna().mean()) if "diff_coins" in df.columns else 1.0
    if miss_rate > 0.85:
        issues.append(f"差枚欠損率異常 {miss_rate:.0%}")
        allow_analysis = False
        severity = "critical"

    if issues and severity != "critical":
        severity = "warning"

    if not allow_analysis:
        severity = "critical"

    if "machine_id" in df.columns and df["machine_id"].nunique() < 3 and len(df) > 50:
        issues.append("台数が極端に少ない — 収集不全の疑い")
        allow_analysis = False
        severity = "critical"

    if "game_type" in df.columns:
        null_gt = int(df["game_type"].isna().sum())
        if null_gt > len(df) * 0.1:
            issues.append(f"game_type欠損 {null_gt}件")
            allow_analysis = False
            severity = "critical"

    return {
        "ok": len(issues) == 0,
        "severity": severity,
        "allow_analysis": allow_analysis,
        "issues": issues,
        "checked_rows": len(df),
        "store_id": store_id,
        "block_ui_recommendations": severity == "critical",
    }
