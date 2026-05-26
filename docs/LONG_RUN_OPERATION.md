# 長時間稼働について

> **重要:** 24時間保証や「検証済み」は、[`soak-test.ps1`](../scripts/soak-test.ps1) の合格レポートと [`data/metrics.csv`](../data/metrics.csv) が揃うまで使わない。  
> 過去の障害分析: [`INCIDENT_STABILITY_REPORT.md`](INCIDENT_STABILITY_REPORT.md)

## 実装している対策（効果はソークで確認すること）

| リスク | 対策 |
|--------|------|
| Redis 未接続で毎回遅延 | メモリキャッシュ即フォールバック |
| 分析ジョブの増殖 | `analysis-loop.ps1` 常駐（1本） |
| cloudflared 複数起動 | 起動前整理・監視 |
| 収集デーモン二重 | `python.exe` のみカウント・重複停止 |
| トンネル一時不通 | 2回連続失敗で tunnel-only 修復 |
| ログ肥大 | 8MB超でローテーション |
| stale プロセス | 1時間ごとに整理 |
| UI 常駐が dev | **`install-stable` 後は `start:public`（BUILD_ID あり）** |

## 必須の検証手順（リリース前）

```powershell
.\scripts\release-stability-gate.ps1 -RunSoakInBackground
.\scripts\check-soak-status.ps1
.\scripts\verify-recurrence-prevention.ps1 -RequireSoakPass -RequireLoadPass
```

詳細: [`STABILITY_GATE.md`](STABILITY_GATE.md)

ソーク合格目安: **UI / API 成功率 ≥ 99%**（レポートは `data/soak-report-*.json`）。

## 監視（時系列）

```powershell
# スーパーバイザーが1時間ごとに追記
Import-Csv data\metrics.csv | Select-Object -Last 30
Get-Content data\tunnel-history.jsonl -Tail 10
Get-Content data\supervisor.log -Tail 30
```

## 想定される限界

- trycloudflare は切断・**URL変更**がありうる（ユーザーにはダウンに見える）
- PCスリープで監視・修復が止まる
- 負荷試験（同時多数クライアント）は**別途**用意が必要
