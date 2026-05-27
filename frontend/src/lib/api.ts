import { cookies } from "next/headers";

import { getInternalApiUrl } from "@/lib/serverApi";

const API_URL = getInternalApiUrl();

async function authHeaders(): Promise<HeadersInit> {
  const jar = await cookies();
  const token = jar.get("helix_token")?.value;
  if (!token) {
    throw new Error("UNAUTHORIZED");
  }
  return { Authorization: `Bearer ${token}` };
}

export type Store = { id: string; name: string; is_active: boolean };

export type TimeSeriesPoint = {
  diff_coins?: number | null;
  rotation_count?: number | null;
};

export type TierType = "recommend" | "hold" | "exclude";

export type RecommendationItem = {
  rank: number;
  machine_id: number;
  title: string;
  machine_number: number;
  score: number;
  tier: TierType;
  reasons: string[];
  sample_count: number;
  period_days: number;
  confidence: number;
  has_missing_data: boolean;
  store_mode?: string | null;
  waveform?: string | null;
  game_type: "slot" | "pachinko";
  icon_variant: string;
  expected_investment?: number | null;
  max_risk_line?: number | null;
  low_risk_zone?: number | null;
  deep_hole_probability?: number | null;
  island_id?: string | null;
  position_type?: string | null;
  week_diff_total?: number | null;
  is_featured?: boolean;
  featured_group?: string | null;
  featured_badge?: string | null;
  daily_big_count?: number | null;
  daily_reg_count?: number | null;
  daily_atari_total?: number | null;
};

export type LiveEvMachine = {
  rank: number;
  machine_id: number;
  machine_number: number;
  title: string;
  game_type: string;
  morning_score: number;
  current_ev: number;
  exhaustion_rate: number;
  ev_delta: number;
  playable: boolean;
  seat_status: string;
  seat_label: string;
  waveform_ml_class: string;
  island_id?: string | null;
  reasons: string[];
  expected_investment?: number | null;
  max_risk_line?: number | null;
  deep_hole_probability?: number | null;
};

export type StoreLiveEv = {
  store_id: string;
  store_name: string;
  target_date: string;
  generated_at: string;
  should_play: boolean;
  danger_level: string; // safe | caution | danger | critical
  danger_score: number;
  danger_headline: string;
  danger_reasons: string[];
  drift_alerts: string[];
  primary: LiveEvMachine | null;
  alternatives: LiveEvMachine[];
  playable_count: number;
  ranked_preview: LiveEvMachine[];
  hot_islands: { island_id: string; temperature: string; ops_rate: number }[];
  quantile?: {
    median_ev?: number;
    upside_ev?: number;
    downside_risk?: number;
    worst_case?: number;
    ev_p50?: number;
  };
  combat_mode?: {
    mode: string;
    label: string;
    should_play: boolean;
    ui_color?: string;
  } | null;
  islands_live?: { island_id: string; state?: string }[];
  manager_warning?: string | null;
  deep_risk?: boolean;
  recommend_score?: number;
  retreat_score?: number;
  collapse_probability?: number;
  island_state?: string;
  retreat_reason?: string[];
  death_line?: number;
  expected_investment?: number;
  fake_release?: boolean;
  trap_wave?: boolean;
  watched?: boolean;
  confidence?: number;
  data_freshness_sec?: number | null;
  stale_warning?: boolean;
  cache_degraded?: boolean;
  recent_drift?: number;
  deep_harami?: boolean;
  median_ev?: number | null;
  downside_ev?: number | null;
  worst_case_ev?: number | null;
};

export type CombatStatus = {
  combat_mode: { mode: string; label: string; should_visit: boolean; should_play: boolean };
  allow_recommendations: boolean;
  integrity: { ok: boolean; issues: string[] };
  anomaly: { alerts: string[] };
};

export type StoreInsight = {
  store_id: string;
  target_date: string;
  danger_level: "safe" | "caution" | "danger";
  danger_score: number;
  should_play: boolean;
  headline: string;
  danger_reasons: string[];
  feature_audit: {
    alerts?: string[];
    diff_dependency_ratio?: number;
    waveform_distribution?: Record<string, number>;
  };
  store_mode?: string | null;
};

export type LiveStatus = {
  store_id: string;
  last_ingest_at: string | null;
  last_analysis_at: string | null;
  log_count_24h: number;
  machine_count: number;
  slot_count: number;
  pachinko_count: number;
  poll_interval_sec: number;
  is_stale: boolean;
  has_any_data: boolean;
  ingest_age_minutes?: number | null;
  sync_age_minutes?: number | null;
  last_sync_at?: string | null;
  analysis_age_minutes?: number | null;
  is_analysis_stale?: boolean;
  realtime_mode?: string;
};

export type CollectorHealth = {
  status: string;
  level: string;
  message: string;
  sources_24h: Record<string, number>;
  active_sources: string[];
  daidata_connected: boolean;
};

export type InsightTrend = {
  posture: string;
  posture_label: string;
  summary: string;
  danger_score?: number | null;
  score_delta?: number | null;
  should_play?: boolean | null;
  headline?: string | null;
  store_mode?: string | null;
};

export type IslandHeatmapCell = {
  island_id: string;
  label: string;
  machine_count: number;
  mean_diff: number;
  ops_rate: number;
  temperature: string;
};

export type EventCalendarDay = {
  date: string;
  day: number;
  weekday: number;
  is_event_day: boolean;
  is_target: boolean;
};

export type StoreExtras = {
  store_id: string;
  collector: CollectorHealth;
  trend: InsightTrend;
  islands: IslandHeatmapCell[];
  events: {
    target_date: string;
    event_days: number[];
    store_mode: string | null;
    store_mode_label: string;
    days: EventCalendarDay[];
  };
};

export type PlayRecord = {
  id: number;
  store_id: string;
  machine_id: number | null;
  machine_number: number;
  title: string;
  game_type: string;
  invest_yen: number;
  result_yen: number;
  note: string;
  played_at: string;
  net_yen: number;
};

export type TodayRecommendations = {
  store_id: string;
  store_name: string;
  target_date: string;
  generated_at: string;
  store_mode?: string | null;
  recommend: RecommendationItem[];
  hold: RecommendationItem[];
  exclude_preview: RecommendationItem[];
  items: RecommendationItem[];
  slot_recommend: number;
  slot_hold: number;
  pachinko_recommend: number;
  pachinko_hold: number;
};

export type MachineDetail = {
  machine_id: number;
  store_id: string;
  store_name: string;
  machine_number: number;
  title: string;
  island_id: string | null;
  position_type: string | null;
  score: number | null;
  tier: string | null;
  reasons: string[];
  sample_count: number;
  period_days: number;
  confidence: number;
  has_missing_data: boolean;
  store_mode: string | null;
  waveform: string | null;
  time_series: Array<{
    captured_at: string;
    diff_coins: number | null;
    rotation_count: number | null;
    big_count: number | null;
    reg_count: number | null;
    final_games: number | null;
    is_operating: boolean | null;
  }>;
  sunk_days: number | null;
  hold_trend: string | null;
  island_injection_history: string | null;
  day_affinity: string | null;
  game_type: "slot" | "pachinko";
  spec_lines: string[];
  daily_big_count?: number | null;
  daily_reg_count?: number | null;
  daily_atari_total?: number | null;
};

export async function fetchStores(): Promise<Store[]> {
  const res = await fetch(`${API_URL}/api/v1/stores`, {
    headers: await authHeaders(),
    next: { revalidate: 300 },
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error("店舗一覧の取得に失敗");
  return res.json();
}

export async function fetchTodayRecommendations(
  storeId: string,
  gameType: "all" | "slot" | "pachinko" = "slot",
): Promise<TodayRecommendations> {
  const res = await fetch(
    `${API_URL}/api/v1/recommendations/today?store_id=${storeId}&game_type=${gameType}`,
    { headers: await authHeaders(), next: { revalidate: 0 } }
  );
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error("推奨一覧の取得に失敗");
  return res.json();
}

export async function fetchMachineDetail(machineId: number): Promise<MachineDetail> {
  const res = await fetch(`${API_URL}/api/v1/machines/${machineId}`, {
    headers: await authHeaders(),
    next: { revalidate: 300 },
  });
  if (res.status === 401) throw new Error("UNAUTHORIZED");
  if (!res.ok) throw new Error("台詳細の取得に失敗");
  return res.json();
}
