"""
全動作確認: 収集メタ → バックフィル → 分析 → API → リアルタイム更新
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

API = os.getenv("API_URL", "http://127.0.0.1:8000")
USER = os.getenv("ADMIN_USERNAME", "helix_admin")
PW = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")
STORES = ["kicona_amagasaki", "maruhan_umeda"]


async def main() -> int:
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        # health
        try:
            r = await client.get(f"{API}/health")
            assert r.status_code == 200, r.text
            print("[ok] health")
        except Exception as e:
            errors.append(f"health: {e}")
            print("[FAIL] API not running — start uvicorn first")
            return 1

        login = await client.post(
            f"{API}/api/v1/auth/login",
            json={"username": USER, "password": PW},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        for STORE in STORES:
            print(f"\n--- store {STORE} ---")
            live1 = (await client.get(f"{API}/api/v1/stores/{STORE}/live-status", headers=h)).json()
            if live1.get("machine_count", 0) < 1:
                if STORE == "maruhan_umeda":
                    print(f"[skip] {STORE} no machines — run seed_maruhan_sample.py")
                    continue
                errors.append(f"{STORE}: no machines")
                continue

            bf = await client.post(f"{API}/api/v1/stores/{STORE}/backfill-game-types", headers=h)
            bf.raise_for_status()
            print(f"[ok] {STORE} backfill: {bf.json()}")

            ar = await client.post(
                f"{API}/api/v1/analysis/run",
                headers=h,
                json={"store_id": STORE, "run_feedback": False},
            )
            ar.raise_for_status()
            print(f"[ok] {STORE} analysis: rec={ar.json().get('recommendations_created')}")

            for gt in ("all", "slot", "pachinko"):
                rec = await client.get(
                    f"{API}/api/v1/recommendations/today",
                    headers=h,
                    params={"store_id": STORE, "game_type": gt},
                )
                rec.raise_for_status()
                body = rec.json()
                n_rec = len(body["recommend"])
                print(
                    f"[ok] {STORE} rec/{gt}: recommend={n_rec} hold={len(body['hold'])} "
                    f"pach_r={body.get('pachinko_recommend')}"
                )
                if gt == "pachinko" and live1.get("pachinko_count", 0) > 10 and n_rec == 0:
                    print(f"[warn] {STORE} pachinko empty recommendations (non-fatal)")
                if gt == "pachinko" and n_rec > 0 and n_rec < 15 and live1.get("pachinko_count", 0) > 30:
                    print(f"[warn] {STORE} pachinko recommend {n_rec}/20")

            lev = await client.get(
                f"{API}/api/v1/stores/{STORE}/live-ev",
                headers=h,
                params={"game_type": "slot"},
            )
            if lev.status_code != 200:
                errors.append(f"{STORE} live-ev {lev.status_code}")
            else:
                lj = lev.json()
                for f in ("combat_mode", "collapse_probability", "retreat_reason", "death_line"):
                    if f not in lj:
                        errors.append(f"{STORE} live-ev missing {f}")
                print(f"[ok] {STORE} live-ev mode={lj.get('combat_mode', {}).get('mode')}")

            ins = await client.get(f"{API}/api/v1/stores/{STORE}/insights/today", headers=h)
            if ins.status_code == 200:
                print(f"[ok] {STORE} insights")
            elif STORE != "maruhan_umeda":
                errors.append(f"{STORE} insights missing")

        STORE = STORES[0]
        gen1 = (await client.get(
            f"{API}/api/v1/recommendations/today",
            headers=h,
            params={"store_id": STORE, "game_type": "slot"},
        )).json()["generated_at"]
        await asyncio.sleep(1)
        await client.post(
            f"{API}/api/v1/analysis/run",
            headers=h,
            json={"store_id": STORE, "run_feedback": False},
        )
        gen2 = (await client.get(
            f"{API}/api/v1/recommendations/today",
            headers=h,
            params={"store_id": STORE, "game_type": "slot"},
        )).json()["generated_at"]

        if gen1 != gen2:
            print(f"[ok] realtime analysis timestamp updated")
        else:
            print("[warn] generated_at unchanged (same second?)")

        live2 = (await client.get(f"{API}/api/v1/stores/{STORE}/live-status", headers=h)).json()
        if live2.get("last_ingest_at"):
            print(f"[ok] live-status ingest={live2['last_ingest_at']} stale={live2['is_stale']}")

    # game_type unit
    from app.game_type import classify_game_type

    assert classify_game_type("スマスロ北斗") == "slot"
    assert classify_game_type("CRパチンコフィーバー源さん") == "pachinko"
    print("[ok] game_type classifier")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("\n=== ALL CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
