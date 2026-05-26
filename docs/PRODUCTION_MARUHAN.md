# マルハン梅田 — 本番運用手順

## 1. 初回セットアップ

```powershell
cd "c:\Helix Victory"

# Docker（任意・推奨）
docker compose up -d redis postgres

# daidata ログイン（手動・1回）
py -3.12 collector/scripts/daidata_login.py
# → ブラウザでログイン後、ターミナルで Enter

# 常駐起動
.\scripts\start_production.ps1
```

## 2. 本番データ収集（Site777 / P-WORLD）

```powershell
py -3.12 scripts/collect_maruhan_live.py
```

`maruhan_umeda.py` は daidata + アナスロ + みんレポ を failover 統合。

## 3. 検証

```powershell
py -3.12 scripts/run_all_tests.py
```

## 4. 環境変数（.env）

| 変数 | 用途 |
|------|------|
| `MARUHAN_UMEDA_URL` | daidata 店舗URL |
| `DAIDATA_STORAGE_STATE` | ログインセッション JSON |
| `ANASLO_MARUHAN_LIST_URL` | アナスロ一覧 |
| `INGEST_API_KEY` | ingest 認証 |

## 5. 開発用シード（daidata 未ログイン時）

```powershell
py -3.12 scripts/seed_maruhan_sample.py
```
