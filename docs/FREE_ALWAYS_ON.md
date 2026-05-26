# 無料で常時公開する方法

## 方式 A: このPCをサーバーにする（完全無料・登録ほぼ不要）

**おすすめ:** すでに動いている構成。PCをつけっぱなしにする。

1. `.\scripts\install-stable.ps1`（スーパーバイザー登録）
2. `Start Helix Victory.bat` をダブルクリック
3. 公開URLは `data\public-url.txt` とデスクトップのショートカット

| メリット | デメリット |
|----------|------------|
| 0円 | PCスリープ不可 |
| クレカ不要 | 再起動で trycloudflare URL が変わる |
| 設定済み | 停電・Windows更新で止まる |

**常時化の設定（Windows）**

- 設定 → システム → 電源 → スリープ **なし**
- `HelixVictorySupervisor` タスクが有効か確認（タスクスケジューラ）

```powershell
.\scripts\install-stable.ps1
.\scripts\register-midnight-cycle.ps1
```

---

## 方式 B: Fly.io（URL固定・24/7・要クレカ登録のみ）

- スクリプト: `.\scripts\deploy-fly-simple.ps1`
- 無料枠あり（クレジットカード登録が必要、課金は枠内なら0円想定）
- 以前はカード未登録でデプロイ不可だった

---

## 方式 C: Oracle Cloud 無料VM（本格常時・要アカウント）

- 登録が必要（以前は手間で見送り）
- 24/7・固定URLに近い運用が可能
- `docs/DEPLOY_FLY_SIMPLE.md` 以外に Oracle 手順は別途検討

---

## 方式 D: Cloudflare 名前付きトンネル（URL固定・要ドメイン）

- ドメイン取得費用のみ（年数百円〜）
- `scripts\install-fixed-tunnel.ps1` / `docs\FIXED_URL.md`

---

## 今すぐやること（無料・PC常時）

```powershell
# 1. 起動スクリプト修正後の確認
powershell -NoProfile -File ".\scripts\start-helix.ps1"

# 2. 常駐登録（未実施なら）
.\scripts\install-stable.ps1

# 3. 動作確認
.\scripts\final-system-test.ps1
```

公開ページ: ログイン後 `http://127.0.0.1:3000/` または trycloudflare の `/welcome`
