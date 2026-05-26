"""クラウド常時稼働用 — 全店舗を1回収集→ingest→分析（GitHub Actions から実行）

部分成功を許容: 1店舗でも ingest できれば exit 0。
認証ミス（401）のみ exit 1。
"""
from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "collector"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# スクレイプ0件でも他店舗が成功すれば続行
os.environ.setdefault("HELIX_LENIENT_COLLECT", "1")


async def _login(api: str, user: str, pw: str):
    import httpx
    from collector.http_retry import is_retryable_http, with_retries

    async def _once():
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(
                f"{api}/api/v1/auth/login",
                json={"username": user, "password": pw},
            )
            r.raise_for_status()
            return r.json()["access_token"]

    return await with_retries(_once, retry_on=is_retryable_http)


async def main() -> int:
    auth_b64 = os.getenv("DAIDATA_AUTH_B64", "").strip()
    auth_path = os.getenv("DAIDATA_STORAGE_STATE", "collector/daidata_auth.json")
    full_auth = ROOT / auth_path
    if auth_b64 and not full_auth.is_file():
        full_auth.parent.mkdir(parents=True, exist_ok=True)
        full_auth.write_bytes(base64.b64decode(auth_b64))

    from collector.config import config
    from collector.ingest_client import post_logs
    from collector.scraper import scrape_store
    import httpx

    api = (os.getenv("HELIX_API_URL") or os.getenv("API_URL", "")).rstrip("/")
    if not api:
        print("FATAL: Set HELIX_API_URL")
        return 1

    for key in ("INGEST_API_KEY", "ADMIN_PASSWORD"):
        if not os.getenv(key, "").strip():
            print(f"FATAL: Missing {key}")
            return 1

    stores = os.getenv("COLLECT_STORES", "kicona_amagasaki,maruhan_umeda").split(",")
    stores = [s.strip() for s in stores if s.strip()]

    ingested = 0
    scraped_rows = 0
    auth_failed = False
    warnings: list[str] = []

    for sid in stores:
        url = config.store_urls.get(sid)
        if not url:
            warnings.append(f"unknown store {sid}")
            continue
        print(f"[collect] {sid} ...")
        try:
            logs = await scrape_store(sid, url)
        except Exception as e:
            warnings.append(f"{sid} scrape: {e}")
            print(f"  scrape skip: {e}")
            continue
        scraped_rows += len(logs)
        print(f"  rows={len(logs)}")
        if not logs:
            continue
        try:
            result = await post_logs(api, sid, logs)
            print(f"  ingest: {result}")
            ingested += 1
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                auth_failed = True
                print(
                    "  ingest 401 — INGEST_API_KEY mismatch. "
                    "Run: .\\scripts\\sync-github-secrets.ps1"
                )
            else:
                warnings.append(f"{sid} ingest HTTP {e.response.status_code}")
                print(f"  ingest failed: {e}")
        except Exception as e:
            warnings.append(f"{sid} ingest: {e}")
            print(f"  ingest failed: {e}")

    user = os.getenv("ADMIN_USERNAME", "helix_admin")
    pw = os.getenv("ADMIN_PASSWORD", "")
    analysis_ok = 0
    if pw:
        try:
            token = await _login(api, user, pw)
            auth_header = {"Authorization": f"Bearer {token}"}
            from collector.http_retry import is_retryable_http, with_retries

            async with httpx.AsyncClient(timeout=180) as c:
                for sid in stores:
                    try:

                        async def _run_analysis(store_id: str = sid):
                            ar = await c.post(
                                f"{api}/api/v1/analysis/run",
                                headers=auth_header,
                                json={"store_id": store_id, "run_feedback": True},
                            )
                            ar.raise_for_status()
                            return ar

                        ar = await with_retries(_run_analysis, retry_on=is_retryable_http)
                        snippet = ar.text[:200]
                        print(f"[analysis] {sid}: HTTP {ar.status_code} {snippet}")
                        analysis_ok += 1
                    except Exception as e:
                        warnings.append(f"{sid} analysis: {e}")
                        print(f"[analysis] {sid} skip: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                auth_failed = True
                print(
                    f"login HTTP {e.response.status_code} — "
                    "run .\\scripts\\sync-github-secrets.ps1 after Fly deploy"
                )
            else:
                warnings.append(f"login: {e}")
        except Exception as e:
            warnings.append(f"login: {e}")
            print(f"analysis login skip: {e}")

    if warnings:
        print("\n--- warnings ---")
        for w in warnings:
            print(f"  - {w}")

    if auth_failed and ingested == 0:
        print("\nFATAL: authentication failed and no data ingested")
        return 1

    if ingested == 0 and scraped_rows == 0 and analysis_ok == 0:
        print("\nWARN: no data ingested (sources may be down) — exit 0 to avoid false alarm")
        return 0

    print(
        f"\nOK: ingested_stores={ingested} scraped_rows={scraped_rows} "
        f"analysis_stores={analysis_ok}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
