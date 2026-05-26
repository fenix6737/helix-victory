# 安定性ゲート（再発防止）

## 一括実行

```powershell
# ビルド + 単体 + 負荷 + 3時間ソーク（前景・約3時間）
.\scripts\release-stability-gate.ps1

# ソークだけバックグラウンド
.\scripts\release-stability-gate.ps1 -SkipBuild -RunSoakInBackground
```

## 個別

| スクリプト | 出力 |
|-----------|------|
| `load-test.ps1` | `data/load-report-*.json` |
| `soak-test.ps1 -Hours 3` | `data/soak-report-*.json`, `data/soak-progress.jsonl` |
| `verify-recurrence-prevention.ps1 -RequireSoakPass -RequireLoadPass` | `data/recurrence-prevention.jsonl` |
| `stability-metrics.ps1` | `data/metrics.csv` |

## ソーク進捗確認

```powershell
.\scripts\check-soak-status.ps1
Get-Content data\soak-run.log -Tail 10
```

## 合格後のみ

以下が揃ったら「検証済み」と言える:

1. `load-report-*.json` → `"pass": true`
2. `soak-report-*.json` → `"pass": true`（UI/API ≥99%）
3. `verify-recurrence-prevention.ps1 -RequireSoakPass -RequireLoadPass` → exit 0

## 週次

```powershell
.\scripts\register-recurrence-check.ps1
```

タスク `HelixVictoryRecurrenceCheck`（日曜 03:00）
