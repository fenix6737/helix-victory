# PC不要・無料で常時稼働する

自宅PCの電源に依存しない構成です。**完全無料**を前提に、次の2パターンを用意しています。

| 方式 | 常時稼働 | 無料 | 難易度 | おすすめ |
|------|----------|------|--------|----------|
| **A. Oracle Cloud 無料VM** | ◎ 24時間 | ◎ Always Free | 中 | **いちばん安定** |
| **B. Fly.io + Neon + GitHub Actions** | ◎ | ◎（枠内） | やや高 | コマンド派向け |

どちらも **Cloudflare トンネル（自宅PC）とは別** で、クラウド上で動きます。

### 固定URLも完全無料で使う

デプロイ後の URL（例: `https://helix-victory.fly.dev`）は **再起動しても変わりません**。  
`.env` に `HELIX_PUBLIC_URL=https://helix-victory.fly.dev` を書くと `data/public-url.txt` に反映されます。

自宅PCの trycloudflare は無料ですが **URLは再起動のたびに変わります**（[FIXED_URL.md](./FIXED_URL.md) 参照）。

---

## 方式A — Oracle Cloud 無料VM（推奨）

Oracle の **Always Free** で ARM VM（24GB RAM）が**ずっと無料**です。  
1台に DB・Redis・アプリをまとめて載せます。

### 1. Oracle アカウント

1. https://www.oracle.com/cloud/free/ でアカウント作成  
2. コンソール → **Compute → Instances → Create**  
3. **Ampere A1**（ARM）、1 OCPU / 6GB RAM 以上、Ubuntu 22.04  
4. パブリックIPを付与、SSH キーを登録  

### 2. VM に Docker を入れる

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER
# 再ログイン後
```

### 3. リポジトリを配置

```bash
git clone <your-repo-url> helix-victory
cd helix-victory
cp deploy/.env.cloud.example deploy/.env.cloud
nano deploy/.env.cloud   # パスワードをすべて変更
```

### 4. 起動

```bash
docker compose -f deploy/docker-compose.cloud.yml --env-file deploy/.env.cloud up -d --build
```

### 5. 公開URL

- ブラウザ: `http://<VMのパブリックIP>:8080/welcome`  
- ログイン: `http://<VMのパブリックIP>:8080/login`  

Oracle の **セキュリティリスト（ファイアウォール）** で TCP **8080** を開いてください。

### 6. データ収集（PC不要）

GitHub にリポジトリを push し、**Secrets** を設定:

| Secret | 内容 |
|--------|------|
| `HELIX_API_URL` | `http://<VMのIP>:8080` または HTTPS 化後のURL |
| `INGEST_API_KEY` | `.env.cloud` と同じ |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | 管理者 |
| `DAIDATA_AUTH_B64` | 下記スクリプトで生成 |

```powershell
# Windows — daidata セッションを Base64 化
[Convert]::ToBase64String([IO.File]::ReadAllBytes("collector\daidata_auth.json"))
```

`.github/workflows/cloud-collect.yml` が **3時間ごと** に収集→ingest→分析します。

---

## 方式B — Fly.io + 無料DB

アプリ本体を Fly.io、DB を Neon、Redis を Upstash（いずれも無料枠）に分けます。

### 1. 無料DB

| サービス | 用途 | URL |
|----------|------|-----|
| [Neon](https://neon.tech) | PostgreSQL | 接続文字列を `DATABASE_URL` に |
| [Upstash](https://upstash.com) | Redis | `REDIS_URL` に（無しでも動作はするがキャッシュ劣化） |

### 2. Fly.io

```bash
# https://fly.io/docs/hands-on/install-flyctl/
fly auth login
cd helix-victory
fly launch --no-deploy --copy-config
# deploy/fly.secrets.example を参考に secrets を設定
fly secrets set DATABASE_URL="postgresql+asyncpg://..." REDIS_URL="..." ADMIN_PASSWORD="..." JWT_SECRET="..." INGEST_API_KEY="..."
fly deploy
```

公開URL: `https://helix-victory.fly.dev`（アプリ名は `fly.toml` で変更可）

`fly.toml` では `auto_stop_machines = "off"` でスリープしない設定にしています。

### 3. GitHub Actions 収集

方式Aと同様に `HELIX_API_URL=https://helix-victory.fly.dev` を Secrets に登録。

---

## 管理者ログイン

| 項目 | 設定場所 |
|------|----------|
| ID | `ADMIN_USERNAME`（初期 `helix_admin`） |
| パスワード | `ADMIN_PASSWORD`（**必ず変更**） |

クラウドでは `.env` / Fly secrets / `deploy/.env.cloud` で管理します。  
**GitHub にパスワードをコミットしないでください。**

---

## 無料の限界（正直な説明）

| 項目 | 内容 |
|------|------|
| **リアルタイム性** | GitHub Actions は最短でも数十分〜数時間間隔。自宅PC+常時daemonより遅い |
| **Fly.io 無料枠** | ポリシー変更の可能性あり。常時ONは Oracle A の方が安心 |
| **台データログイン** | `DAIDATA_AUTH_B64` の期限切れ時は再ログイン→Secret更新 |
| **勝利保証** | なし（分析エンジンのみ） |

---

## 自宅PCトンネルからの移行

1. 方式AまたはBでクラウドを起動  
2. `scripts/seed_maruhan_sample.py` または `cloud_collect_once.py` でデータ投入  
3. スマホのブックマークを **新しいクラウドURL** に差し替え  
4. `publish-public.ps1` / cloudflared は停止してよい（PC不要になる）

---

## 困ったとき

```bash
# VM 上でログ
docker compose -f deploy/docker-compose.cloud.yml logs -f helix

# Fly
fly logs
```

API ヘルス: `https://<your-host>/health`  
実戦ヘルス: `https://<your-host>/health/combat`
