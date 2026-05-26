# Helix Victory — 実戦運用ガイド

## フェーズ定義

| フェーズ | 条件 |
|----------|------|
| MVP〜β | キコーナ1店で収集→分析→UIが通る（現状） |
| 実戦運用β | 2店舗収集 + 自動更新 + パチンコ表示 |
| **実戦レベル** | 上記 + 3ヶ月ログ + 危険日 + 波形 + Feature監査 |

## 最優先（毎日）

```powershell
cd "c:\Helix Victory"
.\scripts\ops_priority1.ps1
```

または手動:

```powershell
# 8000 を解放 → 再起動
cd backend
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ..
py -3.12 scripts/e2e_local.py --store kicona_amagasaki
py -3.12 scripts/verify_all.py
```

### 完了チェック

- `pachinko_count > 0`
- `has_any_data = true`
- パチンコタブで推奨最大20件
- `GET /insights/today` で危険日・Feature監査

## 常駐収集

```powershell
cd collector
py -3.12 -m collector.daemon --stores kicona_amagasaki,maruhan_umeda
```

状態: `collector/state/daemon_state.json`

## マルハン梅田

```powershell
py -3.12 scripts/daidata_login.py
py -3.12 -m collector.run --store maruhan_umeda --once
```

`.env`: `DAIDATA_STORAGE_STATE`, 任意 `DAIDATA_EMAIL` / `DAIDATA_PASSWORD`

## ログ蓄積方針

- **RawLog は削除しない**（ingest は追記のみ）
- 保存: 時刻・差枚・回転・BIG・REG・稼働・波形（分析時付与）・source
- 目標: **3ヶ月以上**（理想 半年〜1年）

## 新API

| パス | 内容 |
|------|------|
| `GET /api/v1/stores/{id}/insights/today` | 危険日判定 + Feature監査 |
| `GET /api/v1/stores/{id}/live-ev?game_type=` | **リアルタイム期待値**（第一/第二/第三候補・空席・島温度） |

## マルハン梅田 Final Combat

- 収集: `maruhan_umeda.py` — daidata + アナスロ + みんレポ（failover）
- `consistency_guard.py` — API/UI/スコア整合
- Redis TTL: live-ev 20s / combat 45s / retreat 20s / island 30s
- テスト: `integrity_suite.py` `stale_suite.py` `collapse_suite.py` `drift_suite.py`

```powershell
py -3.12 -m collector.daemon --stores maruhan_umeda
py -3.12 scripts/integrity_suite.py
```

## 即戦力 v2（実戦即投入）

| モジュール | 内容 |
|-----------|------|
| `combat_mode_engine.py` | **attack / careful / avoid / retreat** |
| `current_ev_engine.py` | 消化率・時間帯補正 |
| `alternative_engine.py` | 同島優先・遠距離飛び禁止 |
| `island_live_engine.py` | heating/active/exhausted/dead/recovery |
| `waveform_ml.py` | fake_release/trap_wave/stable_setting 等 |
| `danger_ml.py` | safe/caution/danger/**critical** |
| `investment_prediction_engine.py` | 予想投資・深ハマリ（初日から） |
| `seat_status_engine.py` | free/occupied/rotating/abandoned/explosive/watched |

モバイル E2E: `cd frontend && npm i && npx playwright install && npm run test:e2e:mobile`

## v3 実戦運用（実戦支援β）

| モジュール | 役割 |
|-----------|------|
| `online_learning_engine.py` | 外した理由・重み更新 |
| `ev_validation_engine.py` | EV改善率検証 |
| `integrity_guardian.py` | データ整合性 — NG時分析停止 |
| `anomaly_guardian.py` | 暴走検知 — 推奨停止 |
| `manager_shift_detector.py` | 店長変更・営業変化 |
| `quantile_ev_engine.py` | p25/p50/p75/p90 |
| `combat_mode_engine.py` | 打てる/慎重/危険/行かない |
| `recovery_engine.py` | API/Redis復旧手順 |
| `combat_history.db` | 実戦スナップショット |
| `waveform_training_pipeline.py` | 長期ログ後の教師学習 |

```powershell
py -3.12 scripts/combat_e2e_suite.py
```

## v2 実戦精度（店舗営業分析エンジン β+）

- `current_ev_engine.py` — 期待値消化率・現在EV
- `alternative_engine.py` — 第二・第三候補
- `waveform_ml.py` — 設定挙動分類
- `machine_family.py` — ジャグ/AT/スマスロ等の重み分離
- `danger_ml.py` — 危険日加重スコア
- `drift_detection.py` — 特徴量ドリフト
- `island_live_engine.py` / `seat_status_engine.py`

## 評価指標（的中率のみ禁止）

- 主: 期待値改善率
- 副: 除外精度・回収回避率・店舗一致率・上位候補平均差枚
