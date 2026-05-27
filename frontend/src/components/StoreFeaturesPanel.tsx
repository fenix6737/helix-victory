"use client";

import { useCallback, useEffect, useState } from "react";
import type { GameKind } from "@/lib/money";
import { formatYen } from "@/lib/money";
import { fetchWithGuard } from "@/lib/uiGuardian";
import { ensureNotifyPermission, notifyHotDay } from "@/lib/notifications";
import type { PlayRecord, StoreExtras } from "@/lib/api";

type Props = {
  storeId: string;
  storeName: string;
  gameKind: GameKind;
  refreshKey?: number;
};

const POSTURE_STYLE: Record<string, string> = {
  attack: "border-emerald-500/40 bg-emerald-950/30 text-emerald-100",
  careful: "border-amber-500/40 bg-amber-950/30 text-amber-100",
  avoid: "border-red-500/40 bg-red-950/30 text-red-100",
  unknown: "border-helix-border bg-helix-surface text-helix-muted",
};

const CAL_STYLE: Record<string, string> = {
  hot: "bg-red-500/35 text-red-100 ring-1 ring-red-300/60",
  high: "bg-amber-500/30 text-amber-100 ring-1 ring-amber-300/50",
  neutral: "bg-black/30 text-helix-muted",
  low: "bg-slate-700/50 text-slate-300",
};

export function StoreFeaturesPanel({ storeId, storeName, gameKind, refreshKey = 0 }: Props) {
  const [open, setOpen] = useState(true);
  const [extras, setExtras] = useState<StoreExtras | null>(null);
  const [records, setRecords] = useState<PlayRecord[]>([]);
  const [notifyOn, setNotifyOn] = useState(false);
  const [form, setForm] = useState({ machine_number: "", invest: "", result: "", note: "" });

  const notifyKey = `helix_notify_hot_only:${storeId}`;
  const lastHotNotifyKey = `helix_last_hot_notified:${storeId}`;

  const load = useCallback(async () => {
    const [ex, pr] = await Promise.all([
      fetchWithGuard<StoreExtras>(`/api/proxy/extras?store_id=${storeId}`, {}, { cacheTtlMs: 45_000 }),
      fetchWithGuard<PlayRecord[]>(`/api/proxy/play-records?store_id=${storeId}`, {}, { cacheTtlMs: 15_000 }),
    ]);
    if (ex.ok) {
      setExtras(ex.data);
      if (notifyOn) {
        const hotToday = ex.data.events.days.find((d) => d.is_target && d.expectancy_level === "hot");
        if (hotToday) {
          const last = localStorage.getItem(lastHotNotifyKey);
          if (last !== hotToday.date) {
            notifyHotDay(storeName, hotToday.date, hotToday.expectancy_score);
            localStorage.setItem(lastHotNotifyKey, hotToday.date);
          }
        }
      }
    }
    if (pr.ok) setRecords(pr.data);
  }, [lastHotNotifyKey, notifyOn, storeId, storeName]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  useEffect(() => {
    const saved = localStorage.getItem(notifyKey);
    if (saved === "1") setNotifyOn(true);
  }, [notifyKey]);

  async function submitRecord(e: React.FormEvent) {
    e.preventDefault();
    const mn = parseInt(form.machine_number, 10);
    if (Number.isNaN(mn)) return;
    const res = await fetch(`/api/proxy/play-records?store_id=${storeId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        store_id: storeId,
        machine_number: mn,
        title: "",
        game_type: gameKind,
        invest_yen: parseInt(form.invest, 10) || 0,
        result_yen: parseInt(form.result, 10) || 0,
        note: form.note,
      }),
    });
    if (res.ok) {
      setForm({ machine_number: "", invest: "", result: "", note: "" });
      void load();
    }
  }

  async function removeRecord(id: number) {
    await fetch(`/api/proxy/play-records/${id}`, { method: "DELETE" });
    void load();
  }

  if (!extras) {
    return (
      <div className="mx-4 mb-2 animate-pulse rounded-xl bg-helix-surface px-3 py-3 text-xs text-helix-muted">
        店舗情報を読み込み中…
      </div>
    );
  }

  const col = extras.collector;
  const trend = extras.trend;
  const target = extras.events.days.find((d) => d.is_target);
  const monthTitle = extras.events.target_date.slice(0, 7);
  const weekDays = ["月", "火", "水", "木", "金", "土", "日"];
  const lead = extras.events.days.length > 0 ? extras.events.days[0].weekday : 0;
  const monthCells: Array<typeof extras.events.days[number] | null> = [
    ...Array.from({ length: lead }, () => null),
    ...extras.events.days,
  ];
  const trail = (7 - (monthCells.length % 7)) % 7;
  monthCells.push(...Array.from({ length: trail }, () => null));
  const colLevel =
    col.level === "error"
      ? "border-red-500/50 bg-red-950/40 text-red-100"
      : col.level === "warn"
        ? "border-amber-500/50 bg-amber-950/40 text-amber-100"
        : "border-emerald-500/30 bg-emerald-950/20 text-emerald-100";

  return (
    <section className="mx-4 mb-3 rounded-xl border border-helix-border/80 bg-black/20">
      <button
        type="button"
        className="flex w-full items-center justify-between px-3 py-2.5 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-sm font-bold text-amber-200/90">店舗サマリー</span>
        <span className="text-helix-muted">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="space-y-2 border-t border-helix-border/60 px-3 pb-3 pt-2">
          <div className={`rounded-lg border px-3 py-2 text-xs ${colLevel}`}>
            <p className="font-semibold">データ収集</p>
            <p className="mt-0.5">{col.message}</p>
            {col.active_sources.length > 0 && (
              <p className="mt-1 opacity-80">接続中: {col.active_sources.join(" / ")}</p>
            )}
          </div>

          <div className={`rounded-lg border px-3 py-2 text-xs ${POSTURE_STYLE[trend.posture] ?? POSTURE_STYLE.unknown}`}>
            <p className="font-bold">{trend.posture_label}</p>
            <p className="mt-1">{trend.summary}</p>
            {trend.score_delta != null && (
              <p className="mt-1 opacity-80">
                危険度 {trend.danger_score}（前日比 {trend.score_delta > 0 ? "+" : ""}
                {trend.score_delta}）
              </p>
            )}
            {extras.events.store_mode_label && (
              <p className="mt-1 opacity-80">店舗モード: {extras.events.store_mode_label}</p>
            )}
          </div>

          <div>
            <p className="text-[10px] text-helix-muted">
              期待値カレンダー（月表示・毎日自動更新）
            </p>
            <p className="mt-1 text-xs font-semibold text-amber-100/90">{monthTitle}</p>
            <div className="mt-1 grid grid-cols-7 gap-1">
              {weekDays.map((w) => (
                <span key={w} className="text-center text-[10px] text-helix-muted">
                  {w}
                </span>
              ))}
              {monthCells.map((d, i) =>
                d ? (
                  <span
                    key={d.date}
                    className={`rounded px-1.5 py-1 text-center text-[10px] tabular-nums ${
                      d.is_target
                        ? "bg-amber-500/30 text-amber-100 ring-1 ring-amber-400/50"
                        : d.is_event_day
                          ? `${CAL_STYLE[d.expectancy_level] ?? CAL_STYLE.neutral} font-semibold`
                          : (CAL_STYLE[d.expectancy_level] ?? CAL_STYLE.neutral)
                    }`}
                    title={`${d.date} ${d.label} (${d.expectancy_score})${d.is_event_day ? " / イベント日" : ""}`}
                  >
                    {d.day}
                    {d.is_event_day ? "★" : ""}
                  </span>
                ) : (
                  <span key={`blank-${i}`} className="rounded bg-transparent px-1.5 py-1 text-[10px]">
                    &nbsp;
                  </span>
                )
              )}
            </div>
            <p className="mt-1 text-[10px] text-helix-muted">
              凡例: 激熱/高期待/様子見/低期待（スコアと危険度・推奨件数から算出）
            </p>
            {target && (
              <p className="mt-1 text-[10px] text-amber-100/90">
                今日: {target.label} ({target.expectancy_score})
                {target.is_event_day ? " / イベント日★" : ""}
              </p>
            )}
          </div>

          {extras.islands.length > 0 && (
            <div>
              <p className="text-[10px] text-helix-muted">島ヒートマップ（7日平均差枚）</p>
              <div className="mt-1 grid grid-cols-3 gap-1 sm:grid-cols-4">
                {extras.islands.slice(0, 12).map((cell) => (
                  <div
                    key={cell.island_id}
                    className={`rounded px-1 py-1 text-center text-[10px] ${
                      cell.temperature === "hot"
                        ? "bg-emerald-500/25 text-emerald-100"
                        : cell.temperature === "cold"
                          ? "bg-red-500/20 text-red-200"
                          : "bg-slate-700/40 text-slate-300"
                    }`}
                  >
                    <div className="truncate">{cell.label}</div>
                    <div className="font-bold tabular-nums">
                      {cell.mean_diff > 0 ? "+" : ""}
                      {cell.mean_diff}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-lg border border-helix-border/60 bg-black/25 px-2 py-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-amber-100/90">自分のプレイ記録</p>
              <button
                type="button"
                className="text-[10px] text-helix-accent"
                onClick={async () => {
                  const ok = await ensureNotifyPermission();
                  setNotifyOn(ok);
                  localStorage.setItem(notifyKey, ok ? "1" : "0");
                }}
              >
                {notifyOn ? "激熱日だけ通知ON" : "激熱日だけ通知"}
              </button>
            </div>
            <form onSubmit={submitRecord} className="mt-2 grid grid-cols-2 gap-2">
              <input
                placeholder="台番"
                value={form.machine_number}
                onChange={(e) => setForm({ ...form, machine_number: e.target.value })}
                className="rounded border border-helix-border bg-helix-surface px-2 py-1.5 text-xs"
                inputMode="numeric"
              />
              <input
                placeholder="投資(円)"
                value={form.invest}
                onChange={(e) => setForm({ ...form, invest: e.target.value })}
                className="rounded border border-helix-border bg-helix-surface px-2 py-1.5 text-xs"
                inputMode="numeric"
              />
              <input
                placeholder="回収(円)"
                value={form.result}
                onChange={(e) => setForm({ ...form, result: e.target.value })}
                className="rounded border border-helix-border bg-helix-surface px-2 py-1.5 text-xs"
                inputMode="numeric"
              />
              <button
                type="submit"
                className="rounded bg-helix-accent/80 py-1.5 text-xs font-bold text-white"
              >
                記録
              </button>
            </form>
            <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto">
              {records.length === 0 && (
                <li className="text-[10px] text-helix-muted">まだ記録がありません</li>
              )}
              {records.map((r) => (
                <li
                  key={r.id}
                  className="flex items-center justify-between text-[10px] text-helix-muted"
                >
                  <span>
                    {r.machine_number}番 · 投資{formatYen(r.invest_yen)} → 回収
                    {formatYen(r.result_yen)}
                    <span className={r.net_yen >= 0 ? " text-emerald-400" : " text-red-400"}>
                      {" "}
                      ({r.net_yen >= 0 ? "+" : ""}
                      {formatYen(Math.abs(r.net_yen))})
                    </span>
                  </span>
                  <button type="button" onClick={() => removeRecord(r.id)} className="text-red-400">
                    削除
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  );
}
