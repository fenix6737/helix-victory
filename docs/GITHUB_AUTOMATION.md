# GitHub Actions 自動化（PC不要）

## よくある間違い（インポートエラー）

**NG:** `https://helix-victory.fly.dev` を Git のクローン元にする  
→ Fly は **Web アプリ** 用。Git は受け付けず `/login` にリダイレクトされ失敗します。

**OK:** GitHub 上のリポジトリ  
→ `https://github.com/あなたのユーザー名/helix-victory.git`

「リポジトリのインポート」で URL を聞かれたら **fly.dev は入れない**。  
代わりに下の `setup-github-automation.ps1` を使う。

## 一発セットアップ

```powershell
cd "c:\Helix Victory"
.\scripts\deploy-fly-simple.ps1   # 未実施なら
.\scripts\setup-github-automation.ps1
```

1. `winget` で GitHub CLI を入れる（未導入時）
2. ブラウザで GitHub ログイン
3. リポジトリ作成 + `git push`
4. Secrets を `deploy\fly-deployed.local.env` から自動登録

## 登録される Secrets

| Secret | 内容 |
|--------|------|
| `HELIX_API_URL` | `https://helix-victory.fly.dev` |
| `INGEST_API_KEY` | Fly デプロイ時生成 |
| `ADMIN_USERNAME` | `helix_admin` |
| `ADMIN_PASSWORD` | Fly デプロイ時生成 |
| `DAIDATA_AUTH_B64` | 任意（`collector\daidata_auth.json` がある場合） |

## 動くワークフロー

| ファイル | スケジュール | 内容 |
|----------|--------------|------|
| `cloud-collect.yml` | 3時間ごと + 手動 | スクレイプ → ingest → 分析（部分成功で緑） |
| `midnight-jst-daily-cycle.yml` | 毎日 00:10 JST | 照合 → 再学習 → 予測レポート |
| `outcome-verify-jst.yml` | 毎日 01〜03 JST | 実績照合のみ |
| `secrets-health-check.yml` | 6時間ごと | 認証・ingest キー整合性チェック |

## Fly 再デプロイ後（必須）

`deploy-fly-simple.ps1` は **既存パスワードを保持** し、終了時に GitHub Secrets を自動同期します。  
手動で直す場合:

```powershell
.\scripts\sync-github-secrets.ps1
```

## 落ちにくくする仕組み

- 収集: 1店舗でも成功すれば成功扱い。ソース403/0件は警告のみ
- API: ログイン・ingest にリトライ（最大4〜5回）
- 認証ミス（401）だけ赤で止まる（Secrets 未同期）

GitHub → **Actions** → **Cloud Collect** → **Run workflow**

成功後: https://helix-victory.fly.dev で統計・予測を確認。

## 注意

- `deploy/fly-deployed.local.env` は **Git に含めない**（`.gitignore` 済み）
- パスワード変更後は `.\scripts\setup-github-automation.ps1 -SkipPush` で Secrets のみ再登録
