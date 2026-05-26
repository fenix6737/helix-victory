# 公開URLと料金（完全無料運営）

## Cloudflare は有料？

| 項目 | 料金 |
|------|------|
| Cloudflare アカウント | **無料** |
| cloudflared トンネル（Quick / 名前付き） | **無料** |
| DNS・SSL（Cloudflare 経由） | **無料** |
| **自分のドメイン名**（例: example.com） | Cloudflare ではなく **レジストラで年数百円〜**（無料ドメインは例外） |

**結論:** Cloudflare 自体に月額を払う必要はありません。  
「固定URL用の名前付きトンネル」だけだと、**ドメイン取得費**が別途かかることが多いです。

---

## 完全無料で固定URLにする

| 方式 | 登録の手間 | 固定URL |
|------|------------|---------|
| **Fly.io（最短）** | Fly だけ（GitHub可） | `https://helix-victory.fly.dev` |
| Oracle VM | Oracle + VM設定 | `http://IP:8080` |
| 自宅PC trycloudflare | **なし** | 再起動で変わる |

**登録がめんどくさい → [DEPLOY_FLY_SIMPLE.md](./DEPLOY_FLY_SIMPLE.md)**（`.\scripts\deploy-fly-simple.ps1`）

Oracle 向け詳細: [DEPLOY_FREE_24x7.md](./DEPLOY_FREE_24x7.md)

デプロイ後 `.env` に追記:

```env
HELIX_PUBLIC_URL=https://helix-victory.fly.dev
```

PCは **データ収集だけ** 回し、ユーザーは Fly の URL にアクセスします。

---

## 自宅PCだけで無料公開（URLは再起動で変わる）

**ダブルクリックで起動（コマンド不要）:**

- `Start Helix Victory.bat` — 起動後に公開URLをダイアログ表示
- デスクトップの `Helix Victory (公開).url` — 起動のたびに最新URLへ更新
- `data/public-url.txt` / welcome 画面の「いまの公開URL」バナー

`trycloudflare.com` の URL は **PC再起動のたびに変わります**（Cloudflare も Helix も無料）。

---

## ドメインを既に持っている場合だけ

Cloudflare に DNS 移管済みなら、PC経由でも **固定URL無料**（Cloudflare 料金なし）:

```powershell
.\scripts\install-fixed-tunnel.ps1 -Hostname helix.あなたのドメイン.com
```

---

## 運用方針の目安

```
完全無料 + 固定URL  →  Fly.io / Oracle（推奨）
完全無料 + PCのみ   →  trycloudflare（URL変動）
ドメイン保有       →  Cloudflare 名前付きトンネル（固定）
```
