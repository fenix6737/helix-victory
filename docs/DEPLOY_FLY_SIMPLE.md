# 固定URLだけ欲しい（Oracle なし・最短）

## 結論

| やりたいこと | おすすめ |
|--------------|----------|
| **固定URL・登録は1回だけ** | **Fly.io**（下のスクリプト） |
| **登録ゼロ** | 自宅PC + trycloudflare（**再起動でURLが変わる**） |

Oracle は運用向きですが、**登録が面倒なら Fly で十分**です。

---

## 何にログインするか

| 種類 | 必要？ |
|------|--------|
| Oracle / Neon / ドメイン | **不要** |
| Fly.io（GitHub 連携可） | **初回だけ** |
| Helix 管理者ログイン | **分析を見るときだけ**（welcome は誰でも開ける） |

「固定URLだけ」＝ **Fly に1回入ってデプロイ → ブックマーク** で終わりです。

---

## 手順（約10分）

### 1. flyctl を入れる

```powershell
winget install flyctl
```

### 2. ワンコマンドデプロイ

```powershell
cd "c:\Helix Victory"
.\scripts\deploy-fly-simple.ps1
```

- ブラウザで Fly にログイン（GitHub 可）
- DB は **SQLite（Fly 内・Neon 不要）**
- 固定URL: `https://helix-victory.fly.dev`

パスワードは `deploy/fly-deployed.local.env` に保存されます。

### 3. ブックマーク

`https://helix-victory.fly.dev/welcome`

自宅PCの `.env` には自動で `HELIX_PUBLIC_URL` が入り、トンネルは不要です。

---

## データ収集

- **PCから**: 今までどおり ingest スクリプトの URL を Fly の URL に変える
- **PC不要**: [DEPLOY_FREE_24x7.md](./DEPLOY_FREE_24x7.md) の GitHub Actions（任意）

---

## 登録すら嫌な場合

```powershell
.\scripts\quick-restart-public.ps1
```

→ 無料・登録なしだが、**PC再起動のたびに URL が変わる**（`data/public-url.txt` を見てブックマーク更新）。

---

## 注意

- Fly は無料枠でも **クレジットカード登録** を求められることがあります（未登録だとアプリ作成不可）
- 登録後: `.\scripts\deploy-fly-simple.ps1`
