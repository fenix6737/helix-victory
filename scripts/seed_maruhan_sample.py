"""マルハン梅田 — ingest（サンプルHTML or キコーナデータ複製）"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))
sys.path.insert(0, str(ROOT / "backend"))

API = os.getenv("API_URL", "http://127.0.0.1:8000")
STORE = "maruhan_umeda"


def _load_logs() -> list[dict]:
    sample = ROOT / "collector" / "samples" / "maruhan_list.html"
    if sample.exists():
        from collector.daidata.parser import parse_all_list_html

        html = sample.read_text(encoding="utf-8", errors="replace")
        rows = parse_all_list_html(html, STORE, hist_num=0)
        if rows:
            return rows

    kicona = ROOT / "collector" / "samples" / "e2e" / "kicona_amagasaki_full.json"
    if not kicona.exists():
        raise FileNotFoundError("Need kicona_amagasaki_full.json or valid maruhan HTML")

    base = json.loads(kicona.read_text(encoding="utf-8"))
    out: list[dict] = []
    pach_titles = [
        "e フィーバー源さん",
        "e からくりサーカス",
        "CR大海物語5",
        "e 新世紀エヴァ",
        "CRぱちんこ押忍",
    ]
    for i, row in enumerate(base):
        r = dict(row)
        r["store_id"] = STORE
        r["source"] = "seed_from_kicona"
        mn = int(r.get("machine_number", i))
        if mn % 97 < 70:
            r["title"] = pach_titles[mn % len(pach_titles)] + f" {mn}"
            r["game_type"] = "pachinko"
        else:
            title = str(r.get("title", ""))
            if "キコーナ" in title:
                title = title.replace("キコーナ", "マルハン梅田")
            r["title"] = title or f"スマスロマルハン {mn}"
            r["game_type"] = "slot"
        out.append(r)
    return out


async def main() -> int:
    logs = _load_logs()
    out_path = ROOT / "collector" / "samples" / "e2e" / "maruhan_umeda_full.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(logs, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] prepared {len(logs)} rows -> {out_path.name}")

    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "HelixVictory2026!Admin")
    key = os.getenv("INGEST_API_KEY", "")
    headers = {"X-Ingest-Key": key} if key else {}

    async with httpx.AsyncClient(timeout=180) as c:
        if (await c.get(f"{API}/health")).status_code != 200:
            print("API not running on :8000")
            return 1
        ing = await c.post(
            f"{API}/api/v1/ingest/logs",
            json={"store_id": STORE, "logs": logs},
            headers=headers,
        )
        ing.raise_for_status()
        print(f"[ok] ingest {ing.json()}")

        login = await c.post(f"{API}/api/v1/auth/login", json={"username": user, "password": pw})
        login.raise_for_status()
        auth = {"Authorization": f"Bearer {login.json()['access_token']}"}

        await c.post(f"{API}/api/v1/stores/{STORE}/backfill-game-types", headers=auth)
        ar = await c.post(
            f"{API}/api/v1/analysis/run",
            headers=auth,
            json={"store_id": STORE, "run_feedback": True},
        )
        ar.raise_for_status()
        body = ar.json()
        print(f"[ok] analysis rec={body.get('recommendations_created')} danger={body.get('danger_level')}")

        lev = await c.get(f"{API}/api/v1/stores/{STORE}/live-ev", headers=auth, params={"game_type": "slot"})
        if lev.status_code != 200:
            print(f"[FAIL] live-ev {lev.status_code}")
            return 1
        lj = lev.json()
        print(f"[ok] live-ev mode={lj.get('combat_mode', {}).get('mode')} primary={lj.get('primary') is not None}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
