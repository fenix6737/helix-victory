"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ExpandableSection } from "@/components/ExpandableSection";
import { MiniChart } from "@/components/MiniChart";
import type { MachineDetail } from "@/lib/api";
import { apiCacheKey, cacheRead, cacheWrite } from "@/lib/offlineCache";
import { formatDiffYen, formatWeekDiff, type GameKind } from "@/lib/money";
import { plainIslandShort, plainPosition, plainText } from "@/lib/plainJapanese";
import { fetchWithGuard } from "@/lib/uiGuardian";

type Props = { machineId: number };

export function MachineDetailView({ machineId }: Props) {
  const router = useRouter();
  const [detail, setDetail] = useState<MachineDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [fromCache, setFromCache] = useState(false);

  const load = useCallback(async () => {
    const key = apiCacheKey(`machine:${machineId}`);
    const cached = cacheRead<MachineDetail>(key);
    if (cached) {
      setDetail(cached);
      setFromCache(true);
      setLoading(false);
    }
    const res = await fetchWithGuard<MachineDetail>(`/api/proxy/machines/${machineId}`, undefined, {
      cacheKey: key,
    });
    if (res.ok) {
      setDetail(res.data);
      cacheWrite(key, res.data);
      setFromCache(!!res.fromCache);
    }
    setLoading(false);
  }, [machineId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !detail) {
    return (
      <main className="mx-auto max-w-lg px-4 py-12 text-center text-helix-muted">
        読み込み中…
      </main>
    );
  }

  if (!detail) {
    return (
      <main className="mx-auto max-w-lg px-4 py-12 text-center">
        <p>台情報を取得できませんでした</p>
        <button type="button" className="mt-4 text-helix-accent" onClick={() => router.back()}>
          戻る
        </button>
      </main>
    );
  }

  const kind: GameKind = detail.game_type === "pachinko" ? "pachinko" : "slot";
  const weekTotal = detail.time_series.reduce(
    (s, p) => s + (p.diff_coins ?? 0),
    0
  );

  return (
    <main className="mx-auto max-w-lg pb-8">
      <header className="sticky top-0 z-10 border-b border-helix-border bg-helix-bg/95 backdrop-blur safe-top">
        <button
          type="button"
          onClick={() => router.back()}
          className="flex min-h-tap w-full items-center px-4 text-body text-helix-accent"
        >
          ← 戻る
        </button>
        <div className="px-4 pb-4">
          <h1 className="text-title">{detail.title}</h1>
          <p className="text-body text-helix-muted">
            {detail.machine_number}番台 · {detail.store_name}
            {fromCache && (
              <span className="ml-2 text-xs text-amber-400">（保存データ）</span>
            )}
          </p>
          {detail.score !== null && (
            <p className="mt-2 text-title">
              おすすめ度 <span className="text-helix-accent">{detail.score}</span>
            </p>
          )}
        </div>
      </header>

      {detail.daily_atari_total != null && (
        <section className="border-b border-helix-border bg-rose-950/20 px-4 py-3">
          <p className="text-sm font-semibold text-rose-200">今日の総当たり</p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-rose-100">
            {detail.daily_atari_total}回
          </p>
          {detail.daily_big_count != null && detail.daily_reg_count != null && (
            <p className="text-xs text-helix-muted">
              BB {detail.daily_big_count} + RB {detail.daily_reg_count}（アナスロ等の当日集計）
            </p>
          )}
        </section>
      )}

      <section className="border-b border-helix-border px-4 py-3">
        <p className="text-sm font-semibold text-amber-200">1週間の出玉（差枚合計）</p>
        <p className="mt-1 text-2xl font-bold tabular-nums text-helix-accent">
          {formatWeekDiff(weekTotal, kind)}
        </p>
        <p className="text-xs text-helix-muted">直近7日 · タップで下のグラフも確認</p>
      </section>

      {kind === "pachinko" && detail.spec_lines.length > 0 && (
        <section className="border-b border-helix-border px-4 py-4">
          <p className="text-meta text-helix-muted">台スペック（名称から抽出）</p>
          <ul className="mt-2 space-y-1 text-body">
            {detail.spec_lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="border-b border-helix-border px-4 py-4">
        <p className="text-meta text-helix-muted">場所</p>
        <p className="mt-1 text-body">
          {plainIslandShort(detail.island_id)} · {plainPosition(detail.position_type)}
        </p>
      </section>

      {detail.reasons.length > 0 && (
        <section className="border-b border-helix-border px-4 py-4">
          <p className="text-meta text-helix-muted">理由</p>
          <ul className="mt-2 space-y-1">
            {detail.reasons.map((r, i) => (
              <li key={i} className="text-body text-helix-muted">
                {plainText(r)}
              </li>
            ))}
          </ul>
        </section>
      )}

      <ExpandableSection title="1週間の出玉グラフ" defaultOpen>
        <MiniChart points={detail.time_series} field="diff_coins" label="差枚（円換算目安）" />
        <p className="mt-2 text-xs text-helix-muted">
          合計 {formatDiffYen(weekTotal, kind)}
        </p>
      </ExpandableSection>

      {kind === "slot" && (
        <ExpandableSection title="回転数">
          <MiniChart points={detail.time_series} field="rotation_count" label="回転数" />
        </ExpandableSection>
      )}
    </main>
  );
}
