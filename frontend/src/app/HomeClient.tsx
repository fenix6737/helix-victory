"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BudgetControl } from "@/components/BudgetControl";
import { CombatPanel } from "@/components/CombatPanel";
import { LiveActivityBar } from "@/components/LiveActivityBar";
import { FeaturedMachinesSection } from "@/components/FeaturedMachinesSection";
import { AccordionSection } from "@/components/AccordionSection";
import { DensityToggle } from "@/components/DensityToggle";
import { DisplaySettingsPanel } from "@/components/DisplaySettingsPanel";
import { EvModeToggle } from "@/components/EvModeToggle";
import { MachineBorderAdmin } from "@/components/MachineBorderAdmin";
import { MachineBottomSheet } from "@/components/MachineBottomSheet";
import { PerformanceDashboard } from "@/components/PerformanceDashboard";
import { RecommendAccuracyPanel } from "@/components/RecommendAccuracyPanel";
import { PeriodStatsPanel } from "@/components/PeriodStatsPanel";
import { RecommendationCard } from "@/components/RecommendationCard";
import { RecommendationRow } from "@/components/RecommendationRow";
import { DensityProvider, useDensity } from "@/lib/density";
import type { RecommendationItem } from "@/lib/api";
import { StoreFeaturesPanel } from "@/components/StoreFeaturesPanel";
import { StoreSwitcher } from "@/components/StoreSwitcher";
import { notifyRecommendationUpdate } from "@/lib/notifications";
import {
  loadGamePreference,
  loadStorePreference,
  saveGamePreference,
  saveStorePreference,
} from "@/lib/preferences";
import { BUDGET_MAX_YEN } from "@/lib/money";
import { ReloadButton } from "@/components/ReloadButton";
import { apiCacheKey, cacheRead, cacheRemove, cacheWrite } from "@/lib/offlineCache";
import { applyBudgetAndRank } from "@/lib/ranking";
import { fetchWithGuard, LIVE_EV_TIMEOUT_MS } from "@/lib/uiGuardian";
import type { LiveStatus, Store, StoreInsight, StoreLiveEv, TodayRecommendations } from "@/lib/api";

type Tab = "recommend" | "hold" | "exclude";
type GameKind = "slot" | "pachinko";

type Props = {
  initialStores: Store[];
  initialStoreId: string;
  initialRecommendations: TodayRecommendations;
};

const POLL_ONLINE_MS = 20_000;
const POLL_OFFLINE_MS = 90_000;
const BUDGET_STORAGE_KEY = "helix_budget_yen";

function cacheKey(storeId: string, kind: GameKind) {
  return `${storeId}:${kind}`;
}

function hydrateFromStorage(
  storeId: string,
  kind: GameKind,
  recCache: React.MutableRefObject<Record<string, TodayRecommendations>>,
  setters: {
    setData: (d: TodayRecommendations) => void;
    setLiveEv: (v: StoreLiveEv | null) => void;
    setLive: (v: LiveStatus | null) => void;
    setInsight: (v: StoreInsight | null) => void;
    setUsingCache: (v: boolean) => void;
  }
) {
  const k = cacheKey(storeId, kind);
  const rec = cacheRead<TodayRecommendations>(apiCacheKey(`rec:${k}`));
  if (rec) {
    recCache.current[k] = rec;
    setters.setData(rec);
    setters.setUsingCache(true);
  }
  const ev = cacheRead<StoreLiveEv>(apiCacheKey(`ev:${k}`));
  if (ev) setters.setLiveEv(ev);
  const live = cacheRead<LiveStatus>(apiCacheKey(`live:${storeId}`));
  if (live) setters.setLive(live);
  const ins = cacheRead<StoreInsight>(apiCacheKey(`insight:${storeId}`));
  if (ins) setters.setInsight(ins);
}

export function HomeClient(props: Props) {
  return (
    <DensityProvider>
      <HomeClientInner {...props} />
    </DensityProvider>
  );
}

function HomeClientInner({
  initialStores,
  initialStoreId,
  initialRecommendations,
}: Props) {
  const { densityClass, sections, isSimple, isDetailed } = useDensity();
  const router = useRouter();
  const [storeId, setStoreId] = useState(initialStoreId);
  const [gameKind, setGameKind] = useState<GameKind>("slot");
  const [data, setData] = useState(initialRecommendations);
  const [live, setLive] = useState<LiveStatus | null>(null);
  const [insight, setInsight] = useState<StoreInsight | null>(null);
  const [liveEv, setLiveEv] = useState<StoreLiveEv | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [usingCache, setUsingCache] = useState(false);
  const [offline, setOffline] = useState(false);
  const [tab, setTab] = useState<Tab>("recommend");
  const [loadingRec, setLoadingRec] = useState(false);
  const [pulse, setPulse] = useState(false);
  const [perfTick, setPerfTick] = useState(0);
  const [budgetYen, setBudgetYen] = useState(BUDGET_MAX_YEN);
  const lastGen = useRef(initialRecommendations.generated_at);
  const recCache = useRef<Record<string, TodayRecommendations>>({
    [cacheKey(initialStoreId, "slot")]: initialRecommendations,
  });
  const abortRef = useRef<AbortController | null>(null);
  const prefsHydrated = useRef(false);
  const touchStartX = useRef<number | null>(null);
  const [sheetItem, setSheetItem] = useState<RecommendationItem | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(BUDGET_STORAGE_KEY);
    if (saved) {
      const n = parseInt(saved, 10);
      if (!Number.isNaN(n)) setBudgetYen(Math.min(BUDGET_MAX_YEN, Math.max(0, n)));
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(BUDGET_STORAGE_KEY, String(budgetYen));
  }, [budgetYen]);

  useEffect(() => {
    cacheWrite(apiCacheKey(`rec:${cacheKey(initialStoreId, "slot")}`), initialRecommendations);
  }, [initialStoreId, initialRecommendations]);

  useEffect(() => {
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  const setters = { setData, setLiveEv, setLive, setInsight, setUsingCache };

  useEffect(() => {
    if (prefsHydrated.current) return;
    prefsHydrated.current = true;
    const sid = loadStorePreference(initialStoreId);
    const defaultGame: GameKind = sid === "maruhan_umeda" ? "pachinko" : "slot";
    const gk = loadGamePreference(defaultGame);
    const kind: GameKind = sid === "maruhan_umeda" ? "pachinko" : gk;
    setStoreId(sid);
    setGameKind(kind);
    hydrateFromStorage(sid, kind, recCache, setters);
  }, [initialStoreId]);

  const fetchRecommendations = useCallback(
    async (
      id: string,
      kind: GameKind,
      signal: AbortSignal,
      silent: boolean,
      force = false
    ) => {
      const key = cacheKey(id, kind);
      if (!silent && !force && recCache.current[key]) setData(recCache.current[key]);
      if (!silent) {
        setLoadingRec(true);
        if (!force && recCache.current[key]) setUsingCache(true);
      }
      const res = await fetchWithGuard<TodayRecommendations>(
        `/api/proxy/recommendations?store_id=${id}&game_type=${kind}`,
        { signal },
        { cacheKey: apiCacheKey(`rec:${key}`), bypassCache: force }
      );
      if (res.ok === false) {
        if (res.error === "unauthorized") {
          router.replace("/login");
          return;
        }
        if (signal.aborted) return;
        if (res.offline && recCache.current[key]) {
          setOffline(true);
          setUsingCache(true);
          if (!silent) setLoadingRec(false);
          return;
        }
        setFetchError(res.error);
        if (!silent) setLoadingRec(false);
        return;
      }
      setFetchError(null);
      setUsingCache(!!res.fromCache);
      if (!res.fromCache && navigator.onLine) setOffline(false);
      const json = res.data;
      recCache.current[key] = json;
      setData(json);
      if (json.generated_at !== lastGen.current) {
        lastGen.current = json.generated_at;
        setPulse(true);
        setTimeout(() => setPulse(false), 900);
        notifyRecommendationUpdate(
          json.store_name,
          json.recommend.length,
          json.recommend[0]?.machine_number
        );
      }
      if (!silent) setLoadingRec(false);
    },
    [router]
  );

  const fetchLive = useCallback(async (id: string, signal: AbortSignal, force = false) => {
    const res = await fetchWithGuard<LiveStatus>(
      `/api/proxy/live-status?store_id=${id}`,
      { signal },
      { cacheKey: apiCacheKey(`live:${id}`), bypassCache: force }
    );
    if (res.ok) setLive(res.data);
  }, []);

  const fetchLiveEv = useCallback(
    async (id: string, kind: GameKind, signal: AbortSignal, force = false) => {
      const key = cacheKey(id, kind);
      const res = await fetchWithGuard<StoreLiveEv>(
        `/api/proxy/live-ev?store_id=${id}&game_type=${kind}`,
        { signal },
        {
          cacheKey: apiCacheKey(`ev:${key}`),
          timeoutMs: LIVE_EV_TIMEOUT_MS,
          bypassCache: force,
        }
      );
      if (res.ok) setLiveEv(res.data);
    },
    []
  );

  const fetchInsight = useCallback(async (id: string, signal: AbortSignal, force = false) => {
    const res = await fetchWithGuard<StoreInsight>(
      `/api/proxy/insights?store_id=${id}`,
      { signal },
      { cacheKey: apiCacheKey(`insight:${id}`), bypassCache: force }
    );
    if (res.ok) setInsight(res.data);
    else if (res.error === "HTTP 404") setInsight(null);
  }, []);

  const clearStoreClientCache = useCallback((id: string, kind: GameKind) => {
    const k = cacheKey(id, kind);
    const other: GameKind = kind === "slot" ? "pachinko" : "slot";
    cacheRemove(apiCacheKey(`rec:${k}`));
    cacheRemove(apiCacheKey(`rec:${cacheKey(id, other)}`));
    cacheRemove(apiCacheKey(`live:${id}`));
    cacheRemove(apiCacheKey(`ev:${k}`));
    cacheRemove(apiCacheKey(`ev:${cacheKey(id, other)}`));
    cacheRemove(apiCacheKey(`insight:${id}`));
    cacheRemove(`perf:${id}:${kind}`);
    cacheRemove(`perf:${id}:${other}`);
    delete recCache.current[k];
    delete recCache.current[cacheKey(id, other)];
  }, []);

  const fetchAll = useCallback(
    (id: string, kind: GameKind, silent = false, force = false) => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      void fetchRecommendations(id, kind, ac.signal, silent, force);
      void fetchLive(id, ac.signal, force);
      void fetchInsight(id, ac.signal, force);
      void fetchLiveEv(id, kind, ac.signal, force);
      return ac;
    },
    [fetchRecommendations, fetchLive, fetchInsight, fetchLiveEv]
  );

  const handleReload = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    setFetchError(null);
    setUsingCache(false);
    clearStoreClientCache(storeId, gameKind);

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    const other: GameKind = gameKind === "slot" ? "pachinko" : "slot";

    try {
      await Promise.all([
        fetchRecommendations(storeId, gameKind, ac.signal, false, true),
        fetchLive(storeId, ac.signal, true),
        fetchInsight(storeId, ac.signal, true),
        fetchLiveEv(storeId, gameKind, ac.signal, true),
        fetchRecommendations(storeId, other, ac.signal, true, true),
      ]);
      setPerfTick((n) => n + 1);
    } finally {
      setRefreshing(false);
    }
  }, [
    refreshing,
    storeId,
    gameKind,
    clearStoreClientCache,
    fetchRecommendations,
    fetchLive,
    fetchInsight,
    fetchLiveEv,
  ]);

  useEffect(() => {
    hydrateFromStorage(storeId, gameKind, recCache, setters);
    fetchAll(storeId, gameKind);
    const other: GameKind = gameKind === "slot" ? "pachinko" : "slot";
    const ac = new AbortController();
    void fetchRecommendations(storeId, other, ac.signal, true);
    return () => {
      abortRef.current?.abort();
      ac.abort();
    };
  }, [storeId, gameKind, fetchAll, fetchRecommendations]);

  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") {
        fetchAll(storeId, gameKind, true);
        setPerfTick((n) => n + 1);
      }
    };
    const ms = offline ? POLL_OFFLINE_MS : POLL_ONLINE_MS;
    const t = setInterval(tick, ms);
    return () => clearInterval(t);
  }, [storeId, gameKind, fetchAll, offline]);

  function onStoreChange(id: string) {
    const kind: GameKind = id === "maruhan_umeda" ? "pachinko" : gameKind;
    if (id === "maruhan_umeda") {
      setGameKind("pachinko");
      saveGamePreference("pachinko");
    }
    saveStorePreference(id);
    const key = cacheKey(id, kind);
    if (recCache.current[key]) setData(recCache.current[key]);
    else hydrateFromStorage(id, kind, recCache, setters);
    setStoreId(id);
  }

  function onGameKindChange(kind: GameKind) {
    if (storeId === "maruhan_umeda" && kind === "slot") {
      /* allow slot tab for maruhan */
    }
    setGameKind(kind);
    saveGamePreference(kind);
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  const rawItems =
    tab === "recommend" ? data.recommend : tab === "hold" ? data.hold : data.exclude_preview;

  const items = useMemo(
    () =>
      tab === "exclude"
        ? applyBudgetAndRank(rawItems, BUDGET_MAX_YEN)
        : applyBudgetAndRank(rawItems, budgetYen),
    [rawItems, budgetYen, tab]
  );

  const displayItems = items;

  function onSwipeEnd(clientX: number) {
    if (touchStartX.current == null) return;
    const dx = clientX - touchStartX.current;
    touchStartX.current = null;
    if (Math.abs(dx) < 56) return;
    const idx = initialStores.findIndex((s) => s.id === storeId);
    if (dx < 0 && idx < initialStores.length - 1) {
      onStoreChange(initialStores[idx + 1].id);
    } else if (dx > 0 && idx > 0) {
      onStoreChange(initialStores[idx - 1].id);
    }
  }

  const formatTime = (iso: string | null | undefined) => {
    if (!iso) return null;
    return new Date(iso).toLocaleTimeString("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Tokyo",
    });
  };

  const listUpdated = formatTime(data.generated_at);
  const hasRecommendations =
    data.recommend.length > 0 || data.hold.length > 0 || data.exclude_preview.length > 0;
  const noStoreData = live != null && !live.has_any_data && !hasRecommendations;
  const isMaruhan = storeId === "maruhan_umeda";
  const pollSec = offline ? POLL_OFFLINE_MS / 1000 : POLL_ONLINE_MS / 1000;
  const storeName =
    initialStores.find((s) => s.id === storeId)?.name ?? data.store_name;

  return (
    <main
      className={`mx-auto max-w-lg pb-8 ${densityClass}`}
      onTouchStart={(e) => {
        touchStartX.current = e.touches[0]?.clientX ?? null;
      }}
      onTouchEnd={(e) => onSwipeEnd(e.changedTouches[0]?.clientX ?? 0)}
    >
      <header className="sticky top-0 z-30 border-b border-helix-border bg-helix-bg/95 backdrop-blur-md safe-top">
        <div className="flex items-center justify-between gap-2 px-4 pt-3">
          <h1 className="bg-gradient-to-r from-blue-400 to-amber-400 bg-clip-text text-title text-transparent">
            推奨台
          </h1>
          <div className="flex shrink-0 items-center gap-2">
            <ReloadButton
              onReload={() => void handleReload()}
              loading={refreshing || loadingRec}
            />
            <button
              type="button"
              onClick={logout}
              className="min-h-tap px-2 text-meta text-helix-muted"
            >
              ログアウト
            </button>
          </div>
        </div>

        <LiveActivityBar
          offline={offline}
          isStale={!!live?.is_stale || (usingCache && !refreshing)}
          noData={!!noStoreData}
          lastIngest={formatTime(live?.last_ingest_at)}
          lastAnalysis={formatTime(live?.last_analysis_at)}
          generatedAt={listUpdated ?? undefined}
          pollingSec={pollSec}
          ingestAgeMin={live?.ingest_age_minutes}
          analysisAgeMin={live?.analysis_age_minutes}
          isAnalysisStale={live?.is_analysis_stale}
        />

        <DensityToggle />
        <DisplaySettingsPanel />

        <p className="px-4 pb-2 text-meta text-helix-muted density-hide-simple">
          {data.store_name} · {data.target_date}
          {listUpdated && <span className="ml-2 text-amber-300/90">更新 {listUpdated}</span>}
        </p>

        <StoreSwitcher stores={initialStores} current={storeId} onChange={onStoreChange} />

        <div className="flex gap-2 px-4 pb-2">
          <button
            type="button"
            onClick={() => onGameKindChange("slot")}
            className={`min-h-tap flex-1 rounded-xl py-2.5 text-meta font-bold ${
              gameKind === "slot"
                ? "bg-amber-500/20 text-amber-300 ring-2 ring-amber-500/50"
                : "bg-helix-surface text-helix-muted"
            }`}
          >
            スロット ({live?.slot_count ?? "…"})
          </button>
          <button
            type="button"
            onClick={() => onGameKindChange("pachinko")}
            className={`min-h-tap flex-1 rounded-xl py-2.5 text-meta font-bold ${
              gameKind === "pachinko"
                ? "bg-pink-500/20 text-pink-300 ring-2 ring-pink-500/50"
                : "bg-helix-surface text-helix-muted"
            }`}
          >
            パチンコ ({live?.pachinko_count ?? 0})
          </button>
        </div>

        <div className="flex border-y border-helix-border bg-helix-bg">
          {(
            [
              ["recommend", "推奨"],
              ["hold", "保留"],
              ["exclude", "除外"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`min-h-tap flex-1 py-3.5 text-sm font-bold ${
                tab === key
                  ? gameKind === "pachinko"
                    ? "tab-pachinko-active border-b-2 text-pink-200"
                    : "tab-slot-active border-b-2 text-amber-200"
                  : "text-helix-muted"
              }`}
            >
              {label}
              <span className="ml-1 text-xs opacity-80">
                {key === "recommend"
                  ? applyBudgetAndRank(data.recommend, budgetYen).length
                  : key === "hold"
                    ? applyBudgetAndRank(data.hold, budgetYen).length
                    : data.exclude_preview.length}
              </span>
            </button>
          ))}
        </div>

        <BudgetControl budgetYen={budgetYen} onChange={setBudgetYen} />
      </header>

      {sections.combat && (
        <div className="density-hide-simple">
          <CombatPanel
            liveEv={liveEv}
            fetchError={fetchError}
            stale={usingCache || offline}
            gameKind={gameKind}
          />
        </div>
      )}

      <EvModeToggle storeId={storeId} />

      {sections.accuracy && (
        <AccordionSection
          id="accuracy"
          title="推奨精度（期待値モード）"
          summary="直近7日のプラス率"
          defaultOpen={false}
          lazyLoad
        >
          <RecommendAccuracyPanel
            storeId={storeId}
            gameKind={gameKind}
            refreshKey={perfTick}
          />
        </AccordionSection>
      )}

      {sections.stats && (
        <AccordionSection
          id="stats-perf"
          title="実績ダッシュボード"
          summary="推奨・保留の的中率"
          defaultOpen={false}
          lazyLoad
        >
          <PerformanceDashboard
            storeId={storeId}
            gameKind={gameKind}
            refreshKey={perfTick}
          />
        </AccordionSection>
      )}

      {sections.stats && !isSimple && (
        <AccordionSection
          id="stats-period"
          title="日次・週次・月次統計"
          defaultOpen={false}
          lazyLoad
        >
          <PeriodStatsPanel storeId={storeId} refreshKey={perfTick} />
        </AccordionSection>
      )}

      {isDetailed && <MachineBorderAdmin />}

      {sections.features && (
        <div className="density-hide-simple">
          <StoreFeaturesPanel
            storeId={storeId}
            storeName={storeName}
            gameKind={gameKind}
            refreshKey={perfTick}
          />
        </div>
      )}

      {loadingRec && !usingCache && (
        <p className="px-4 py-2 text-center text-meta text-helix-muted animate-pulse">
          一覧を更新中…
        </p>
      )}

      {fetchError && !loadingRec && (
        <div className="mx-4 mt-2 rounded-xl border border-red-500/40 bg-red-950/40 px-3 py-2 text-xs text-red-200">
          一覧の取得に失敗しました: {fetchError}
        </div>
      )}

      {noStoreData && !offline && (
        <div className="mx-4 mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-4 text-body text-amber-100">
          {isMaruhan ? (
            <p>マルハン梅田 — データ準備中です。しばらくお待ちください。</p>
          ) : (
            <p>データ準備中です。</p>
          )}
        </div>
      )}

      {!loadingRec && !noStoreData && items.length === 0 && (
        <div className="px-4 py-12 text-center text-meta text-helix-muted">
          {tab === "recommend"
            ? `予算内の${gameKind === "slot" ? "スロット" : "パチンコ"}推奨がありません（予算を上げるか保留を確認）`
            : "該当なし"}
        </div>
      )}

      {!noStoreData && tab === "recommend" && !isSimple && data.recommend.length > 0 && (
        <FeaturedMachinesSection items={data.recommend} />
      )}

      {!noStoreData && displayItems.length > 0 && (
        <section>
          {tab === "recommend" && (
            <p className="border-b border-helix-border/60 px-4 py-2 text-xs font-semibold text-amber-200/90">
              推奨 {displayItems.length}台（おすすめ度順）
            </p>
          )}
          {displayItems.map((item, i) =>
            isSimple || tab !== "recommend" ? (
              <RecommendationRow
                key={item.machine_id}
                item={item}
                onSelect={setSheetItem}
                showTier={tab !== "recommend"}
                compact={isSimple}
              />
            ) : (
              <RecommendationCard
                key={item.machine_id}
                item={item}
                showTier={tab !== "recommend"}
                pulse={pulse && tab === "recommend" && i < 3}
              />
            )
          )}
        </section>
      )}

      <MachineBottomSheet item={sheetItem} onClose={() => setSheetItem(null)} />

      <footer className="px-4 py-6 text-center text-meta text-helix-muted">
        毎日自動更新 · {pollSec}秒ごとに再取得
      </footer>
    </main>
  );
}
