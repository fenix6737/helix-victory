"""整合性監査スイート"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

API = os.getenv("API_URL", "http://127.0.0.1:8000")
STORE = os.getenv("E2E_STORE", "kicona_amagasaki")
USER = os.getenv("ADMIN_USERNAME", "helix_admin")
PW = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")


async def main() -> int:
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=60) as c:
        login = await c.post(f"{API}/api/v1/auth/login", json={"username": USER, "password": PW})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

        for store in (STORE, "maruhan_umeda"):
            lev = await c.get(f"{API}/api/v1/stores/{store}/live-ev", headers=auth, params={"game_type": "slot"})
            if lev.status_code == 404:
                print(f"[skip] {store} live-ev 404 — run seed_maruhan_sample.py")
                continue
            if lev.status_code != 200:
                errors.append(f"{store} live-ev {lev.status_code}")
                continue
            j = lev.json()
            from app.analysis.consistency_guard import audit_consistency
            import pandas as pd

            rep = audit_consistency(df=pd.DataFrame(), store_id=store, live_ev_payload=j, recommendations_count=1)
            if (
                rep.get("severity") == "critical"
                and not rep.get("allow_recommendations")
                and j.get("should_play")
            ):
                errors.append(f"{store} critical consistency mismatch")
            print(f"[ok] consistency {store} issues={len(rep.get('issues', []))}")

    if errors:
        print("FAILED:", errors)
        return 1
    print("=== INTEGRITY SUITE PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
