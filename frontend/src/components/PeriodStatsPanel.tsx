"use client";

import { useEffect, useState } from "react";
import { fetchWithGuard } from "@/lib/uiGuardian";

type StatsPayload = { store_id: string; period: string; data: Record<string, unknown> };

type Props = { storeId: string };

export function PeriodStatsPanel({ storeId }: Props) {
  const [daily, setDaily] = useState<StatsPayload | null>(null);
  const [weekly, setWeekly] = useState<StatsPayload | null>(null);
  const [monthly, setMonthly] = useState<StatsPayload | null>(null);
  const [tab, setTab] = useState<"daily" | "weekly" | "monthly">("daily");

  useEffect(() => {
    const ac = new AbortController();
    void (async () => {
      const [d, w, m] = await Promise.all([
        fetchWithGuard<StatsPayload>(`/api/proxy/statistics/daily?store_id=${storeId}`, { signal: ac.signal }),
        fetchWithGuard<StatsPayload>(`/api/proxy/statistics/weekly?store_id=${storeId}`, { signal: ac.signal }),
        fetchWithGuard<StatsPayload>(`/api/proxy/statistics/monthly?store_id=${storeId}`, { signal: ac.signal }),
      ]);
      if (d.ok) setDaily(d.data);
      if (w.ok) setWeekly(w.data);
      if (m.ok) setMonthly(m.data);
    })();
    return () => ac.abort();
  }, [storeId]);

  const active =
    tab === "daily" ? daily?.data : tab === "weekly" ? weekly?.data : monthly?.data;

  const pred = (active?.prediction as Record<string, unknown>) ?? {};
  const hitPct = pred.hit_rate_pct as number | null | undefined;

  return (
    <section className="mx-4 mt-4 rounded-xl border border-helix-border bg-helix-card/80 p-4">
      <h2 className="text-title text-helix-text">統計ダッシュボード</h2>
      <div className="mt-2 flex gap-2">
        {(["daily", "weekly", "monthly"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              tab === t ? "bg-amber-500/30 text-amber-100" : "bg-helix-border text-helix-muted"
            }`}
          >
            {t === "daily" ? "1日" : t === "weekly" ? "週" : "月"}
          </button>
        ))}
      </div>
      {!active ? (
        <p className="mt-3 text-meta text-helix-muted">統計を読み込み中…</p>
      ) : (
        <div className="mt-3 space-y-2 text-sm text-helix-text">
          {tab === "daily" && (
            <>
              <p>稼働台: {(active.machine_count as number) ?? 0} / 大当たり合計: {(active.big_hit_total as number) ?? 0}</p>
              <p>本日の予測台数: {(active.recommendation_count as number) ?? 0}</p>
            </>
          )}
          {tab === "weekly" && Array.isArray(active.hit_rate_trend) && (
            <>
              <p>
                7日的中率推移:{" "}
                {(active.hit_rate_trend as { date: string; hit_rate_pct: number | null }[])
                  .map((x) => `${x.date.slice(5)}:${x.hit_rate_pct ?? "-"}%`)
                  .join(" ")}
              </p>
              {Array.isArray(active.machine_ranking) &&
                (active.machine_ranking as { machine_number: number; diff_sum: number; is_featured?: boolean }[])
                  .length > 0 && (
                  <p className="text-meta text-helix-muted">
                    台別ランキング TOP:{" "}
                    {(active.machine_ranking as { machine_number: number; diff_sum: number; is_featured?: boolean }[])
                      .slice(0, 5)
                      .map((m) => `${m.machine_number}番(${m.diff_sum})${m.is_featured ? "★" : ""}`)
                      .join(" / ")}
                  </p>
                )}
            </>
          )}
          {tab === "monthly" && (
            <>
              <p>
                月間評価件数: {(pred.evaluated as number) ?? 0}（{String(active.start_date)}〜
                {String(active.end_date)}）
              </p>
              {Array.isArray(active.machine_family_trends) &&
                (active.machine_family_trends as { group: string; samples: number }[]).length > 0 && (
                  <p className="text-meta text-helix-muted">
                    機種別傾向:{" "}
                    {(active.machine_family_trends as { group: string; samples: number }[])
                      .slice(0, 4)
                      .map((f) => `${f.group}:${f.samples}件`)
                      .join(" / ")}
                  </p>
                )}
            </>
          )}
          <p className="text-amber-200">
            的中率: {hitPct != null ? `${hitPct}%` : "データ不足"}
            {pred.recommend_hit_rate_pct != null &&
              ` / 推奨枠 ${pred.recommend_hit_rate_pct as number}%`}
          </p>
        </div>
      )}
    </section>
  );
}
