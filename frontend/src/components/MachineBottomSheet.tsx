"use client";

import { useEffect } from "react";
import { MachineIcon } from "@/components/MachineIcon";
import type { RecommendationItem } from "@/lib/api";
import { formatBetYen, formatWeekDiff, MONEY_LABEL, rateLabel } from "@/lib/money";
import { formatWhyLine, plainIslandShort, plainPosition, plainText } from "@/lib/plainJapanese";

type Props = {
  item: RecommendationItem | null;
  onClose: () => void;
};

export function MachineBottomSheet({ item, onClose }: Props) {
  useEffect(() => {
    if (!item) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [item]);

  if (!item) return null;

  const kind = item.game_type === "pachinko" ? "pachinko" : "slot";
  const whyLine = formatWhyLine(item.reasons, item.position_type, item.waveform ?? null);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end bg-black/55"
      role="dialog"
      aria-modal
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] overflow-y-auto rounded-t-2xl border border-helix-border bg-helix-bg pb-safe shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto my-2 h-1 w-10 rounded-full bg-helix-border" />
        <div className="flex items-start gap-3 px-4 pb-4 pt-2">
          <MachineIcon title={item.title} gameType={kind} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="text-lg font-bold">{item.title}</p>
            <p className="text-sm text-amber-200">{item.machine_number}番 · {item.rank}位</p>
            <p className="mt-1 text-xs text-emerald-200/90">{whyLine}</p>
            <p className="text-[10px] text-helix-muted">
              {plainIslandShort(item.island_id)} · {plainPosition(item.position_type)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-h-tap rounded-lg px-2 text-helix-muted"
            aria-label="閉じる"
          >
            ✕
          </button>
        </div>
        <div className="space-y-3 border-t border-helix-border px-4 py-4">
          <p className="text-body">
            おすすめ度 <span className="font-black text-emerald-400">{item.score}</span>
          </p>
          {item.week_diff_total != null && (
            <p className="text-sm text-helix-muted">
              7日出玉 {formatWeekDiff(item.week_diff_total, kind)}
            </p>
          )}
          <ul className="space-y-1">
            {item.reasons.map((r, i) => (
              <li key={i} className="text-xs text-helix-muted">
                {plainText(r)}
              </li>
            ))}
          </ul>
          {item.expected_investment != null && (
            <div className="rounded-lg border border-helix-border bg-black/25 p-3 text-sm">
              <p className="text-[10px] text-helix-muted">{rateLabel(kind)}</p>
              <p>
                {MONEY_LABEL.bet}{" "}
                <span className="font-bold text-helix-accent">
                  {formatBetYen(item.expected_investment, kind)}
                </span>
              </p>
            </div>
          )}
          <a
            href={`/machines/${item.machine_id}`}
            className="block rounded-xl bg-helix-accent py-3 text-center text-sm font-bold text-white"
          >
            台詳細ページを開く
          </a>
        </div>
      </div>
    </div>
  );
}
