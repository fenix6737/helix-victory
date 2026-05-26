"use client";

import { useEffect, useState } from "react";
import type { GameKind } from "@/lib/money";
import { fetchWithGuard } from "@/lib/uiGuardian";

type PerfData = {
  recommend: {
    days_7: { plus_rate_pct: number | null; prediction_count: number; plus_count: number };
    daily_7: { date: string; plus_rate_pct: number; count: number }[];
  };
  operations: { outcomes_total: number };
  target_plus_rate_pct: number;
  ev_mode: boolean;
  last_reconcile_count?: number;
};

type Props = { storeId: string; gameKind: GameKind; refreshKey?: number };

export function RecommendAccuracyPanel({ storeId, gameKind, refreshKey = 0 }: Props) {
  const [data, setData] = useState<PerfData | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    void (async () => {
      const res = await fetchWithGuard<PerfData>(
        `/api/proxy/performance?store_id=${storeId}&game_type=${gameKind}`,
        { signal: ac.signal }
      );
      if (res.ok) setData(res.data);
    })();
    return () => ac.abort();
  }, [storeId, gameKind, refreshKey]);

  if (!data) return null;

  const rate = data.recommend.days_7.plus_rate_pct;
  const target = data.target_plus_rate_pct ?? 55;
  const daily = data.recommend.daily_7 ?? [];
  const ok = rate != null && rate >= target;

  return (
    <section className="mx-4 mb-3 rounded-xl border border-cyan-500/40 bg-cyan-950/20 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-title text-cyan-100">推奨精度（期待値モード）</h2>
          <p className="mt-1 text-[11px] text-cyan-200/70">
            推奨枠の翌日プラス率 — 目標 {target}% 以上
            {data.ev_mode ? "" : "（オカルトモード中）"}
          </p>
        </div>
        <p
          className={`text-3xl font-black tabular-nums ${
            rate == null ? "text-helix-muted" : ok ? "text-emerald-400" : "text-amber-300"
          }`}
        >
          {rate != null ? `${rate}%` : "—"}
        </p>
      </div>
      <p className="mt-2 text-xs text-helix-muted">
        7日: プラス {data.recommend.days_7.plus_count}/{data.recommend.days_7.prediction_count}件
        · 照合累計 {data.operations.outcomes_total}件
      </p>
      {daily.length > 0 && (
        <div className="mt-3 flex h-16 items-end gap-1">
          {daily.map((d) => {
            const h = Math.max(4, Math.min(100, (d.plus_rate_pct / 100) * 56));
            const above = d.plus_rate_pct >= target;
            return (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-0.5">
                <div
                  className={`w-full rounded-t ${above ? "bg-emerald-500" : "bg-amber-600/80"}`}
                  style={{ height: `${h}px` }}
                  title={`${d.date}: ${d.plus_rate_pct}%`}
                />
                <span className="text-[9px] text-helix-muted">{d.date.slice(8)}</span>
              </div>
            );
          })}
        </div>
      )}
      <div
        className="mt-1 border-t border-dashed border-cyan-500/30"
        style={{ marginTop: -18, height: 0, position: "relative", top: -30 }}
        aria-hidden
      />
    </section>
  );
}
