"use client";

import { useEffect, useState } from "react";
import type { GameKind } from "@/lib/money";
import { fetchWithGuard } from "@/lib/uiGuardian";

type Block = {
  sample_days: number;
  prediction_count: number;
  plus_count: number;
  plus_rate_pct: number | null;
  avg_diff: number | null;
};

type PerfData = {
  store_id: string;
  game_type: string;
  generated_at: string;
  definition: string;
  disclaimer: string;
  recommend: {
    days_7: Block;
    days_30: Block;
    daily_7: { date: string; plus_rate_pct: number; count: number }[];
  };
  hold: { days_7: Block; days_30: Block };
  operations: {
    last_ingest_at: string | null;
    last_analysis_at: string | null;
    logs_24h: number;
    is_stale: boolean;
    has_data: boolean;
    outcomes_total: number;
  };
};

type Props = { storeId: string; gameKind: GameKind; refreshKey?: number };

function RateCard({
  label,
  block,
}: {
  label: string;
  block: Block;
}) {
  const rate = block.plus_rate_pct;
  const lowSample = block.prediction_count < 5;
  return (
    <div className="rounded-lg border border-helix-border/80 bg-black/25 px-3 py-2">
      <p className="text-[10px] text-helix-muted">{label}</p>
      <p
        className={`text-2xl font-black tabular-nums ${
          rate == null ? "text-helix-muted" : rate >= 55 ? "text-emerald-400" : "text-amber-300"
        }`}
      >
        {rate != null ? `${rate}%` : "—"}
      </p>
      <p className="text-[10px] text-helix-muted">
        プラス {block.plus_count}/{block.prediction_count}件
        {lowSample && " · データ少"}
      </p>
    </div>
  );
}

export function PerformanceDashboard({ storeId, gameKind, refreshKey = 0 }: Props) {
  const [open, setOpen] = useState(true);
  const [data, setData] = useState<PerfData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    void (async () => {
      const res = await fetchWithGuard<PerfData>(
        `/api/proxy/performance?store_id=${storeId}&game_type=${gameKind}`,
        { signal: ac.signal },
        { cacheKey: `perf:${storeId}:${gameKind}`, cacheTtlMs: 60_000 }
      );
      if (res.ok) {
        setData(res.data);
        setError(null);
      } else if (res.error !== "aborted") {
        setError(res.error);
      }
    })();
    return () => ac.abort();
  }, [storeId, gameKind, refreshKey]);

  if (!data && !error) {
    return (
      <div className="mx-4 mb-2 animate-pulse rounded-xl bg-helix-surface px-3 py-4 text-center text-xs text-helix-muted">
        実績を集計中…
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-4 mb-2 rounded-xl border border-red-500/30 bg-red-950/30 px-3 py-2 text-xs text-red-200">
        実績取得: {error}
      </div>
    );
  }

  if (!data) return null;

  const ops = data.operations;
  const updated = new Date(data.generated_at).toLocaleTimeString("ja-JP", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <section className="mx-4 mb-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20">
      <button
        type="button"
        className="flex min-h-tap w-full items-center justify-between px-3 py-2.5 text-left"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div>
          <p className="text-sm font-bold text-emerald-200">実績ダッシュボード</p>
          <p className="text-[10px] text-helix-muted">
            自動更新 · 照合 {ops.outcomes_total}件 · {updated}
          </p>
        </div>
        <span className="text-helix-muted">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-emerald-500/20 px-3 pb-3">
          <p className="mt-2 text-[10px] leading-snug text-helix-muted">{data.definition}</p>

          <p className="mt-2 text-xs text-amber-100/90">
            {ops.is_stale ? "分析更新待ち" : "バックグラウンド稼働中"}
            {ops.logs_24h > 0 && ` · 24h収集 ${ops.logs_24h}件`}
          </p>

          <p className="mt-2 text-xs font-semibold text-emerald-300/90">推奨 — プラス率</p>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <RateCard label="直近7日" block={data.recommend.days_7} />
            <RateCard label="直近30日" block={data.recommend.days_30} />
          </div>

          <p className="mt-3 text-xs font-semibold text-amber-200/80">保留 — プラス率</p>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <RateCard label="直近7日" block={data.hold.days_7} />
            <RateCard label="直近30日" block={data.hold.days_30} />
          </div>

          {data.recommend.daily_7.length > 0 && (
            <div className="mt-3">
              <p className="text-[10px] text-helix-muted">推奨の日別プラス率（7日）</p>
              <div className="mt-1 flex flex-wrap gap-1">
                {data.recommend.daily_7.map((d) => (
                  <span
                    key={d.date}
                    className="rounded bg-black/30 px-1.5 py-0.5 text-[10px] tabular-nums text-amber-100"
                  >
                    {d.date.slice(5)}: {d.plus_rate_pct}%
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="mt-3 text-[10px] text-helix-muted">{data.disclaimer}</p>
        </div>
      )}
    </section>
  );
}
