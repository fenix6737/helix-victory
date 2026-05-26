# 開発者向け指示書 — 実装対応表

**原則:** ダミー・サンプル実装禁止。実装後は必ず `.\scripts\developer-spec-test.ps1` で全項目を検証すること。

## 1. データソース

| URL | 用途 | 実装 |
|-----|------|------|
| ana-slo キコーナ尼崎一覧 | 台別データ | `collector/collector/anaslo/` |
| pscube c713842 | 出玉情報 | `collector/collector/pscube/` |
| min-repo タグ | 補完 | `collector/collector/minrepo/` |
| hall-navi hid | ホール情報 | `collector/collector/hallnavi/` |

統合: `collector/collector/kicona.py` — 欠損は `data_sources` に記録し API メタデータへ送信。

環境変数（`.env` / GitHub Secrets）:

```
ANASLO_KICONA_LIST_URL=https://ana-slo.com/ホールデータ/兵庫県/キコーナ尼崎本店-データ一覧/
MINREPO_TAG_URL=https://min-repo.com/tag/キコーナ尼崎本店/
PSCUBE_KICONA_URL=https://www.pscube.jp/dedamajyoho-P-townDMMpachi/c713842/
HALLNAVI_KICONA_URL=https://hall-navi.com/hole_view?hid=660088400000027290
```

リアルタイム:

| 環境 | 方式 |
|------|------|
| 自宅PC常時 | `python -m collector.daemon`（45〜180秒ポーリング） |
| PC不要 | GitHub Actions `cloud-collect.yml`（3時間ごと） |

**GitHub 自動化（push + Secrets）:** `.\scripts\setup-github-automation.ps1` → [GITHUB_AUTOMATION.md](./GITHUB_AUTOMATION.md)

ingest: `POST /api/v1/ingest/logs`（Fly では Next.js rewrite 経由で到達）

## 2. 大当たり予測

| 要件 | 実装 |
|------|------|
| 毎日複数台予測 | `run_analysis` → `recommendations` |
| 翌日実績照合・的中率 | `feedback.record_outcomes` |
| 深夜0時以降レポート | `DailyPredictionReport` + `midnight-daily-cycle.ps1` |
| 日次学習サイクル | `POST /api/v1/analysis/daily-learning-cycle` |

自動実行（PC不要）:

- GitHub Actions: `.github/workflows/midnight-jst-daily-cycle.yml`（00:10 JST）
- 手動: `.\scripts\midnight-daily-cycle.ps1`（`HELIX_PUBLIC_URL` 対応）

## 3. 統計（1日 / 週 / 月）

| 統計 | API | UI |
|------|-----|-----|
| 1日 | `GET .../statistics/daily` | `PeriodStatsPanel` 1日タブ |
| 週 | `GET .../statistics/weekly` | 7日的中率推移・台別ランキング TOP |
| 月 | `GET .../statistics/monthly` | 月間評価・機種別傾向 |

## 4. 注目機種

- 判定: `backend/app/featured.py`（東京喰種・エヴァ）
- UI: `FeaturedMachinesSection.tsx` + カードバッジ

## 5. 検証（必須）

```powershell
# ユニット + Fly 実API（deploy\fly-deployed.local.env を使用）
.\scripts\developer-spec-test.ps1

# データ未投入時は先に同期
.\scripts\sync-fly-data.ps1

# 全体
.\scripts\final-system-test.ps1
```

| テスト | 内容 |
|--------|------|
| `collector/tests/test_developer_spec_sources.py` | §1 URL・統合 |
| `backend/tests/test_developer_spec_period.py` | §3 統計構造 |
| `backend/tests/test_developer_spec_cycle.py` | §2 日次サイクル |
| `backend/tests/test_featured.py` | §4 注目機種 |

## 6. 起動

- `scripts/start-helix.ps1` / `Start Helix Victory.bat`
- Fly 固定URL: `.\scripts\deploy-fly-simple.ps1`
