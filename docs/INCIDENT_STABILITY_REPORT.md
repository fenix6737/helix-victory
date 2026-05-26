# 安定性インシデント報告（根拠付き）

**作成日:** 2026-05-25  
**事象:** 実運用で約2〜3時間後に「サーバーダウン」相当の障害  
**前提:** 以前の「長時間稼働検証済み」表現は、**24時間ソーク・負荷試験・時系列メトリクス・再発防止確認ログ**が揃っていなかった。本書はその事実を認めた上での証跡整理である。

---

## 1. 提出証跡一覧

| 項目 | 有無 | 根拠ファイル / 備考 |
|------|------|---------------------|
| サーバーログ | **あり** | `data/api.log`（約1950行・主に `/health`）、`data/frontend.log`（約3300行） |
| クラッシュログ | **専用ファイルなし** | OSクラッシュダンプ未検出。実質は `frontend.log` の例外スタックがクラッシュ相当 |
| メモリ使用量推移 | **時系列なし** | スナップショットのみ（`long-run-audit.ps1` 実行時点）。**継続記録は未実装だった** |
| CPU使用率推移 | **なし** | 収集機構なし |
| API失敗率 | **限定的** | `api.log` はほぼ `GET /health 200`。業務APIの失敗率ログは**未集計** |
| 接続数推移 | **なし** | netstat/接続カウンタの記録なし |
| 再起動履歴 | **あり（間接）** | `data/autostart.log`, `data/supervisor.log`, `frontend.log` の再起動行 |
| インフラ制限 | **あり（仕様）** | trycloudflare 無料トンネル・PC常時起動・Windows ローカルプロセス |
| 負荷試験 | **未実施** | リポジトリ内に k6/ab/vegeta 等の負荷試験スクリプト**なし** |
| 長時間稼働テスト | **未実施（公式）** | `long-run-audit.ps1` は**単発スナップショット**（数秒）のみ |

---

## 2. サーバーログ（抜粋・根拠）

### 2.1 フロントエンド — 起動直後の致命エラー（`start:public` + 壊れた `.next`）

`data/frontend.log` 先頭:

```
> next start -H 0.0.0.0 -p 3000
⚠ "next start" does not work with "output: standalone" configuration.
⨯ [Error: Cannot find module './611.js']
EvalError: Code generation from strings disallowed for this context
  at ... middleware.js
```

- `Cannot find module './611.js'` は **12回**記録（チャンク不整合）。
- この状態では `/welcome` が **HTTP 500** になり得る（後述 autostart と一致）。

### 2.2 フロントエンド — 常駐モードが dev である証拠

同一ログ内で **`dev:public` / `next dev` が複数回**起動。開発サーバは:

- ファイル監視により **`next.config.ts` 変更で再起動**（ログ行: `Found a change in next.config.ts. Restarting the server`）。
- 長時間稼働に向かない挙動（メモリ増・コンパイル中の一時不通）。

### 2.3 フロントエンド — ヘルスプローブ結果（ログ内集計）

| 指標 | 値 | 算出元 |
|------|-----|--------|
| `GET /welcome 200` | **1821** | `frontend.log` |
| `GET /welcome` 非200 | **0** | 同上（プローブ成功分のみ。障害瞬間は別セッションのログに分散の可能性） |

※スーパーバイザーは60秒ごとに curl するため、ログ末尾は連続200が多い。

### 2.4 API — 再起動回数

`data/api.log` 内の `Started server process` は **3回**（プロセスID: 37312, 2960, 11212）。  
**明示的な Traceback / OOM / Fatal は api.log 内に未検出**（APIプロセス自体のクラッシュログは薄い）。

### 2.5 自動起動・修復ログ — UI 500 と修復ループ

`data/autostart.log`（2026-05-24 10:56〜11:01）:

```
Port 3000 unhealthy (HTTP 500) — restarting frontend
===== autostart begin (mode=both repair=True) =====  （4回連続）
Stopped cloudflared pid ... （5プロセス）
```

**再現性の高い障害パターン:** UI が500 → 全面修復 → cloudflared 複数停止 → トンネルURL変更。

### 2.6 スーパーバイザー — 「OK」とユーザー体感の乖離

`data/supervisor.log`（2026-05-25）:

- 07:44 フル修復後、**07:51 / 08:02 / 08:41 にトンネル単独修復**（URLが都度変更）。
- 08:28〜20:45 は **30分ごとに `OK api=True ui=True tunnel=True`**（ローカルヘルスは通過）。

**重要:** ローカル `127.0.0.1:3000/welcome` が200でも、  
**古い trycloudflare URL・トンネル切断・UI500の瞬間**ではユーザーからは「ダウン」に見える。

### 2.7 公開URL変更履歴（インフラ側）

`data/public-url.json` / `autostart.log` より:

| 時刻（ログ） | URL（抜粋） |
|-------------|-------------|
| 07:51:11 | `poor-messages-speak-advertising.trycloudflare.com` |
| 08:02:33 | `mystery-michigan-railroad-quote.trycloudflare.com` |
| 08:41:47 | `und-instrumental-theater-way.trycloudflare.com` |

**無料クイックトンネルはセッション単位でURLが変わる。** ブックマーク・PWA・共有リンクは無効化される。

### 2.8 Windows アプリケーションクラッシュログ

直近48時間、`node` / `python` / `cloudflared` 関連の **Application Error (Level=2) は0件**（調査時点）。  
→ **OSレベルのクラッシュより、アプリ論理エラー・トンネル切替・devサーバ不安定が主因**と判断。

---

## 3. メモリ / CPU / 接続数 / API失敗率

| 項目 | 状態 |
|------|------|
| メモリ推移 | **記録なし**。監査時点のみ例: Python ~178MB, Node ~380MB（2026-05-24 調査時） |
| CPU推移 | **記録なし** |
| 接続数 | **記録なし** |
| API失敗率 | **未集計**。`final-system-test.ps1` は**手動・単発**13チェックのみ |

→ **監視設計不足**（感度の高い SLO 未定义、時系列DB/CSVなし）。

---

## 4. 実施済みだった検証（事実）

| 検証 | 内容 | 限界 |
|------|------|------|
| `final-system-test.ps1` | 起動直後の13項目（HTTP200・応答時間・ログイン・API） | **数分以内のスナップショット** |
| `long-run-audit.ps1` | プロセス数・メモリ瞬間値・SQLiteサイズ | **24hソークではない** |
| `supervisor.log` | 60秒ヘルス（local + tunnel reachability） | **業務API・外部クライアント視点の失敗率なし** |
| `backend/tests` unittest | 4件程度 | 負荷・長時間なし |
| Redisフォールバック修正 | 遅延防止 | プロセス死活・UI500は別問題 |

---

## 5. 未検証・確認漏れ（事実）

1. **3時間以上のソークテスト**（成功率・p95レイテンシの時系列）  
2. **負荷試験**（同時接続・ポーリング20s×Nクライアント）  
3. **CPU/メモリの連続サンプリング**  
4. **本番ビルドUIでの常駐**（`install-stable` 後も autostart が `dev:public` デフォルトだった）  
5. **トンネルURL変更時のクライアント通知・自動追従**  
6. **修復時の cloudflared 多重停止→URL断絶**のユーザー影響評価  
7. **分析ループ常駐**のプロセス生存（初期は `Start-Job` でセッション依存）  
8. **クラッシュダンプ・構造化障害ログ**（JSONL / metrics.csv）  

---

## 6. 障害原因（根拠に基づく結論）

### 主因 A: フロントエンド常駐方式が本番向きでなかった

- `next dev`（`dev:public`）での常駐、または壊れた `.next` による `next start` 失敗（`./611.js` / middleware EvalError）。
- autostart ログで **HTTP 500 → 修復ループ**が記録されている。

### 主因 B: 無料 trycloudflare のセッション切れ・URL変更

- 2〜3時間運用でトンネル修復が複数回発生し、**公開URLが変わる**。
- ユーザーは「サーバーが落ちた」と認識しうる（実際は**別URLに移行**）。

### 主因 C: 監視が「ローカル200」中心で、SLO未達を検知できなかった

- スーパーバイザーは長時間 `OK` を記録しうるが、**古いURL・UI500・dev再起動**をユーザー影響として集計していなかった。

### 補足: API・メモリ枯渇の直接証拠は薄い

- `api.log` に OOM/例外なし。メモリも監査閾値内のスナップショットのみ。  
→ **「メモリリークで落ちた」は未証明**。主因は UI とトンネル。

---

## 7. 再現条件

1. Windows PC で `HelixVictorySupervisor` または手動 autostart が動作。  
2. フロントが `dev:public`、または不完全な `next build` 成果物で `start:public`。  
3. 公開アクセスが trycloudflare URL に依存。  
4. 2時間以上経過、または `next.config.ts` 等の変更で dev サーバが再起動。  
5. トンネル一時不通 → スーパーバイザーが tunnel-only repair → **URL変更**。

---

## 8. 修正内容（本対応で実装・予定）

| 対応 | 内容 |
|------|------|
| 本番UIデフォルト | `frontend/.next/BUILD_ID` がある場合は `start:public` を使用（`helix-autostart.ps1`） |
| メトリクス収集 | `scripts/stability-metrics.ps1` → `data/metrics.csv`（1分サンプル） |
| ソークテスト | `scripts/soak-test.ps1`（既定3時間・成功率レポート） |
| スーパーバイザー | 1時間ごとにメトリクス追記、トンネルURL変更を `data/tunnel-history.jsonl` に記録 |
| ドキュメント | 本報告書、`LONG_RUN_OPERATION.md` の過大表現を削除 |

**未完了（検証ログ待ち）:** 3時間ソークの合格レポート、負荷試験、再発防止の運用確認。

---

## 9. 再発防止策

1. **常駐は `npm run build` + `start:public` のみ**（`install-stable.ps1` 後）。dev 常駐は開発時のみ。  
2. **`data/metrics.csv` を常時追記**し、メモリ・CPU・ヘルスを事後分析可能にする。  
3. **リリース前に `soak-test.ps1 -Hours 3` 必須**（成功率 ≥99%、tunnel/UI/API 個別）。  
4. **トンネルURL変更時**は `public-url.json` 更新＋デスクトップショートカット再生成（既存）に加え、履歴ログで追跡。  
5. **「検証済み」表現は soak 合格CSV・レポート添付時のみ**使用。

---

## 10. 長時間稼働テスト結果（実績）

| テスト | 実施 | 結果 |
|--------|------|------|
| 公式24hソーク | **未実施** | — |
| supervisor 連続OKログ | 2026-05-25 に **約12時間分**の local OK（30分間隔） | トンネル修復3回・URL変更あり |
| long-run-audit 単発 | 実施 | その時点OK（プロセス数等） |
| ユーザー報告の2〜3hダウン | **事象あり** | 上記 A+B+C と整合 |

---

## 11. 参照コマンド

```powershell
Get-Content data\autostart.log | Select-String "500|repair|unhealthy"
Get-Content data\supervisor.log | Select-String "UNHEALTHY|Tunnel"
Get-Content data\frontend.log | Select-String "Error|Cannot find module|Restarting"
Import-Csv data\metrics.csv | Select-Object -Last 20
.\scripts\soak-test.ps1 -Hours 3 -IntervalSec 60
```
