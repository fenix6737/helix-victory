"use client";

import { MachineIcon } from "@/components/MachineIcon";
import type { RecommendationItem } from "@/lib/api";
import { useDensity } from "@/lib/density";
import { formatBetYen } from "@/lib/money";

type Props = {
  item: RecommendationItem;
  onSelect: (item: RecommendationItem) => void;
  compact?: boolean;
  showTier?: boolean;
};

const TIER_LABEL: Record<string, string> = {
  recommend: "推奨",
  hold: "保留",
  exclude: "除外",
};

export function RecommendationRow({ item, onSelect, compact, showTier }: Props) {
  const { mode, isDetailed } = useDensity();
  const kind = item.game_type === "pachinko" ? "pachinko" : "slot";
  const slim = compact || mode === "simple";

  return (
    <button
      type="button"
      onClick={() => onSelect(item)}
      className={`flex w-full items-center gap-3 border-b border-helix-border px-4 py-3 text-left transition active:bg-helix-surface/80 ${
        kind === "pachinko" ? "hover:bg-pink-950/20" : "hover:bg-amber-950/15"
      }`}
    >
      <span className="w-8 shrink-0 text-center text-lg font-black tabular-nums text-emerald-400">
        {item.rank}
      </span>
      <MachineIcon title={item.title} gameType={kind} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.title}</p>
        <p className="text-xs text-amber-200/90">
          {item.machine_number}番
          {showTier && (
            <span className="ml-2 text-helix-muted">{TIER_LABEL[item.tier]}</span>
          )}
        </p>
        {!slim && (
          <p className="mt-0.5 text-xs text-helix-muted">
            期待値 {item.score}
            {item.expected_investment != null &&
              ` · 目安 ${formatBetYen(item.expected_investment, kind)}`}
          </p>
        )}
        {isDetailed && item.reasons[0] && (
          <p className="mt-1 line-clamp-2 text-[10px] text-helix-muted">{item.reasons[0]}</p>
        )}
      </div>
      <span className="shrink-0 text-xs text-helix-muted">›</span>
    </button>
  );
}
