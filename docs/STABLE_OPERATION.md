# 常時安定運用（自宅PC）

## セットアップ（1回）

```powershell
cd "c:\Helix Victory"
.\scripts\install-stable.ps1
```

## 仕組み（100%安定を目指す構成）

| 層 | 内容 |
|----|------|
| **スーパーバイザー** | ログオン45秒後から常駐、**60秒ごと**に API/UI/トンネルを監視・自動復旧 |
| **起動ロック** | 同時起動の競合を防止（再起動直後の二重起動対策） |
| **SQLite 優先** | Postgres 待ちで API が落ちない（`HELIX_USE_POSTGRES=1` でのみ Postgres） |
| **本番 UI** | `npm run build` 済みなら `start:public`（dev より高速・安定） |
| **3回リトライ** | 起動失敗時 45秒間隔で最大3回再試行 |
| **URL 自動更新** | デスクトップ `.url` / `public-url.txt` / welcome バナー |

ログ: `data/supervisor.log` / `data/autostart.log` / `data/api.log` / `data/frontend.log`

## 確認

```powershell
.\scripts\verify-stable.ps1
```

## 手動起動

`Start Helix Victory.bat` — URL ダイアログ付き

## 解除

```powershell
.\scripts\uninstall-autostart.ps1
```

## 限界

PC **電源 ON 中**の安定性は上記で最大化。  
**PC 電源 OFF** や **固定 URL** はクラウド（Fly/Oracle）が必要。
