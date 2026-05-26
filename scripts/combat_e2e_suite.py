"""
実戦 E2E 戦闘テスト — ingest / analysis / live_ev / combat-status / 整合性

  py -3.12 scripts/combat_e2e_suite.py
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

API = os.getenv("API_URL", "http://127.0.0.1:8000")
USER = os.getenv("ADMIN_USERNAME", "helix_admin")
PW = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")
STORE = os.getenv("E2E_STORE", "kicona_amagasaki")


async def main() -> int:
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            h = await client.get(f"{API}/health")
            assert h.status_code == 200
            print("[ok] health")
        except Exception as e:
            print(f"[FAIL] API: {e}")
            return 1

        ch = await client.get(f"{API}/health/combat")
        if ch.status_code == 404:
            ch = await client.get(f"{API}/api/v1/health/combat")
        if ch.status_code == 200:
            print(f"[ok] combat health: {ch.json().get('status')}")
        else:
            errors.append(f"combat health {ch.status_code}")

        login = await client.post(
            f"{API}/api/v1/auth/login",
            json={"username": USER, "password": PW},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        ar = await client.post(
            f"{API}/api/v1/analysis/run",
            headers=auth,
            json={"store_id": STORE, "run_feedback": True},
        )
        ar.raise_for_status()
        body = ar.json()
        print(f"[ok] analysis blocked={body.get('blocked')} combat={body.get('combat_mode', {}).get('mode')}")

        if body.get("blocked"):
            errors.append("analysis blocked unexpectedly")

        for gt in ("slot", "pachinko"):
            rec = await client.get(
                f"{API}/api/v1/recommendations/today",
                headers=auth,
                params={"store_id": STORE, "game_type": gt},
            )
            rec.raise_for_status()
            rj = rec.json()
            n = len(rj["recommend"]) + len(rj["hold"])
            print(f"[ok] recommendations {gt}: {n}")
            if gt == "pachinko" and rj.get("pachinko_count", 0) > 0 and n == 0:
                errors.append("pachinko has machines but no rec")

        lev = await client.get(
            f"{API}/api/v1/stores/{STORE}/live-ev",
            headers=auth,
            params={"game_type": "slot"},
        )
        if lev.status_code == 200:
            lj = lev.json()
            print(
                f"[ok] live-ev primary={lj.get('primary') is not None} "
                f"alts={len(lj.get('alternatives', []))} quantile={bool(lj.get('quantile'))}"
            )
            cm = lj.get("combat_mode", {}) or {}
            if cm.get("mode") not in ("attack", "careful", "avoid", "retreat", None):
                errors.append(f"live-ev combat mode {cm.get('mode')}")
            if lj.get("danger_level") == "critical" and lj.get("should_play"):
                errors.append("critical must force should_play=false")
            for field in (
                "combat_mode",
                "collapse_probability",
                "island_state",
                "retreat_reason",
                "death_line",
            ):
                if field not in lj:
                    errors.append(f"live-ev missing {field}")
            if lj.get("primary") and not lj.get("alternatives") and lj.get("retreat_reason"):
                pass
        else:
            errors.append(f"live-ev {lev.status_code}")

        cs = await client.get(f"{API}/api/v1/stores/{STORE}/combat-status", headers=auth)
        if cs.status_code == 200:
            cj = cs.json()
            cm = cj.get("combat_mode", {}).get("mode")
            print(f"[ok] combat-status mode={cm}")
            if cm not in ("attack", "careful", "avoid", "retreat", None):
                errors.append(f"unknown combat mode {cm}")
            if not cj.get("integrity", {}).get("allow_analysis", True):
                errors.append("integrity blocks analysis")
        else:
            errors.append(f"combat-status {cs.status_code}")

        ins = await client.get(f"{API}/api/v1/stores/{STORE}/insights/today", headers=auth)
        if ins.status_code != 200:
            errors.append("insights missing")

    # integrity unit
    from app.analysis.integrity_guardian import audit_data_integrity
    import pandas as pd

    bad = audit_data_integrity(pd.DataFrame(), STORE)
    if bad.get("allow_analysis"):
        errors.append("empty df should block")
    else:
        print("[ok] integrity blocks empty")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("\n=== COMBAT E2E PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
