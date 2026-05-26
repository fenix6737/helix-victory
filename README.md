# Helix Victory — 店舗特化型 高期待値抽出エンジン

マルハン梅田店・キコーナ尼崎本店向け。単台差枚予測ではなく、**店舗営業パターン・島単位・時系列・配置**を統合し、低期待値を除外して高期待値候補の再現性を最大化する。

**勝利保証はしません。** 相対評価エンジンです。

## 管理者アクセス

サイトは常時公開想定ですが、**管理者ログイン必須**です。

| 項目 | デフォルト値（`.env` で変更） |
|---|---|
| 管理者ID | `helix_admin` |
| パスワード | `HelixVictory2026!Admin` |

本番では必ず `ADMIN_PASSWORD` / `JWT_SECRET` / `INGEST_API_KEY` を変更してください。

**公開と認証**: `/welcome` は誰でも閲覧可（常時公開）。分析画面（`/` など）は管理者ログイン必須。未ログイン時は `/welcome` へ誘導します。

## 出力区分

| 区分 | 意味 |
|---|---|
| **推奨** | サンプル十分・店舗/島/時系列一致・除外条件クリア |
| **保留** | 要確認（スコア中間帯） |
| **除外** | 回収傾向・死に位置・稼働不足・波形異常など |

## データソース（本番・ダミーなし）

| 店舗 | ソース |
|---|---|
| マルハン梅田店 | 台データオンライン `207042`（要プレミアムログイン） |
| キコーナ尼崎本店 | アナスロ + みんレポ + みんパチ（複合） |

キコーナ尼崎本店の参照URL:

| 役割 | URL |
|---|---|
| アナスロ（主・全台BB/RB） | https://ana-slo.com/ホールデータ/兵庫県/キコーナ尼崎本店-データ一覧/ |
| みんレポ（補完） | https://min-repo.com/3093761/ （タグ一覧から過去分も） |
| みんパチ（旧イベント日） | https://minpachi.com/キコーナ尼崎本店/ |

同一日・同一台番はアナスロ優先でマージします。

## 分析レイヤー（engine_v2）

1. 基礎統計（差枚・回転・BIG/REG・稼働）
2. 時系列挙動（凹み・速度・時間帯）
3. 店舗癖（特定日・曜日・営業モード）
4. 配置（角/角2/通路/末尾推定）
5. 島相関（島単位必須・単台単独判定禁止）
6. 除外ロジック + 波形分類（右肩/V字/一撃/死亡/放出）

## 日次学習ループ

```
予測保存 → 実結果取得 → 誤差記録 → 重み再調整 → 翌日分析
```

```bash
python backend/scripts/daily_loop.py maruhan_umeda
```

## クイックスタート

```bash
docker compose up -d
cp .env.example .env

cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

cd frontend && npm install && npm run dev
# http://localhost:3000/login
```

### スマホ・他端末から公開

**PCを消しても常時稼働（無料）** → [docs/DEPLOY_FREE_24x7.md](docs/DEPLOY_FREE_24x7.md)（Oracle 無料VM または Fly.io + GitHub Actions）

**PC起動・ログオン時に自動稼働:**

```powershell
.\scripts\install-autostart.ps1   # 一度だけ実行
# 解除: .\scripts\uninstall-autostart.ps1
```

ログオン約30秒後に API・画面・収集・トンネルが起動します。URL は `data/public-url.txt`、ログは `data/autostart.log`。

**自宅PCをサーバーにする（手動で今すぐ起動）:**

```powershell
.\scripts\publish-public.ps1
```

| 方式 | 説明 |
|---|---|
| **LAN** | 同じ Wi-Fi 内 → `http://<PCのIP>:3000` |
| **インターネット** | Cloudflare 無料トンネル → `https://xxxx.trycloudflare.com` |

公開 URL は `data/public-url.txt` に保存されます。

### 収集

```bash
cd collector && pip install -r requirements.txt
playwright install chromium

# マルハン（台データ・要ログイン）
python scripts/daidata_login.py
python -m collector.run --store maruhan_umeda --once

# キコーナ尼崎本店（アナスロ巡回 + みんレポ補完）
python -m collector.run --store kicona_amagasaki --once
```

`.env` の `INGEST_API_KEY` を collector にも設定してください。

### 分析

```bash
curl -X POST http://localhost:8000/api/v1/analysis/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"store_id\":\"kicona_amagasaki\"}"
```

## API

| メソッド | パス | 認証 |
|---|---|---|
| POST | `/api/v1/auth/login` | なし |
| GET | `/api/v1/recommendations/today` | 管理者JWT |
| POST | `/api/v1/ingest/logs` | `X-Ingest-Key` |
| POST | `/api/v1/stores/{id}/metadata` | 管理者JWT または `X-Ingest-Key` |
| POST | `/api/v1/analysis/run` | 管理者JWT |
| POST | `/api/v1/analysis/daily-loop` | 管理者JWT |
