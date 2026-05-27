"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { MachineIcon } from "@/components/MachineIcon";
import type { RecommendationItem } from "@/lib/api";
import {
  formatBetYen,
  formatWeekDiff,
  MONEY_LABEL,
  rateLabel,
} from "@/lib/money";
import {
  formatWhyLine,
  plainIslandShort,
  plainPosition,
  plainTextForGame,
} from "@/lib/plainJapanese";

type Props = { item: RecommendationItem; showTier?: boolean; pulse?: boolean };

const TIER_STYLE: Record<string, string> = {
  recommend: "tier-recommend",
  hold: "tier-hold",
  exclude: "tier-exclude",
};

const TIER_LABEL: Record<string, string> = {
  recommend: "推奨",
  hold: "保留",
  exclude: "除外",
};

export function RecommendationCard({ item, showTier, pulse }: Props) {
  const [showSpec, setShowSpec] = useState(false);
  const tierClass = TIER_STYLE[item.tier] ?? TIER_STYLE.recommend;
  const isPachinko = item.game_type === "pachinko";
  const kind = isPachinko ? "pachinko" : "slot";
  const whyLine = formatWhyLine(
    item.reasons,
    item.position_type,
    item.waveform ?? null,
    kind
  );
  const specBadges = useMemo(() => {
    const src = [item.title, ...(item.spec_lines ?? []), item.spec_summary ?? ""].join(" ");
    const tags = new Set<string>();
    if (/AT|ART/i.test(src)) tags.add("AT/ART");
    if (/Aタイプ/.test(src)) tags.add("Aタイプ");
    if (/\bLT\b/i.test(src)) tags.add("LT");
    const m = src.match(/1\/\d{2,4}/);
    if (m) tags.add(m[0]);
    if (kind === "pachinko") tags.add("パチンコ");
    else tags.add("スロット");
    return Array.from(tags).slice(0, 4);
  }, [item.title, item.spec_lines, item.spec_summary, kind]);

  return (
    <Link
      href={`/machines/${item.machine_id}`}
      prefetch
      scroll={false}
      className={`card-enter block border-b px-4 py-5 transition active:scale-[0.99] ${
        isPachinko ? "card-pachinko" : "card-slot"
      } ${pulse ? "card-pulse" : ""}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex w-14 shrink-0 flex-col items-center">
          <span className={`text-2xl font-black tabular-nums ${tierClass}`}>
            {item.rank}
          </span>
          <span className="text-[10px] text-helix-muted">位</span>
          <span className="mt-1 text-sm font-bold text-amber-200">{item.machine_number}番</span>
        </div>
        <MachineIcon
          title={item.title}
          gameType={kind}
          size="md"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-title truncate">{item.title}</p>
            {item.is_featured && item.featured_badge && (
              <span className="rounded-full bg-amber-500/30 px-2 py-0.5 text-xs font-bold text-amber-100">
                {item.featured_badge}
              </span>
            )}
            {showTier && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tierClass}`}>
                {TIER_LABEL[item.tier]}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs font-medium text-emerald-200/95">{whyLine}</p>
          <p className="mt-0.5 text-[10px] text-amber-200/80">
            {plainIslandShort(item.island_id)} · {plainPosition(item.position_type)}
          </p>
          {specBadges.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {specBadges.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-sky-400/40 bg-sky-900/30 px-2 py-0.5 text-[10px] font-semibold text-sky-100"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {item.spec_summary && (
            <p className="mt-0.5 text-[10px] text-sky-200/85">{item.spec_summary}</p>
          )}
          {(item.spec_lines?.length ?? 0) > 0 && (
            <span
              onClick={(e) => {
                e.preventDefault();
                setShowSpec((v) => !v);
              }}
              className="mt-1 inline-block cursor-pointer text-[10px] font-semibold text-sky-300 underline underline-offset-2"
            >
              {showSpec ? "スペック詳細を閉じる" : "スペック詳細をタップで展開"}
            </span>
          )}
          {showSpec && (item.spec_lines?.length ?? 0) > 0 && (
            <ul className="mt-1 space-y-0.5 rounded-md border border-sky-500/30 bg-sky-950/20 px-2 py-1">
              {item.spec_lines?.map((line, i) => (
                <li key={i} className="text-[10px] text-sky-100/90">
                  {line}
                </li>
              ))}
            </ul>
          )}
          {item.daily_atari_total != null && (
            <p className="mt-1 text-xs font-semibold text-rose-200/95">
              今日の総当たり {item.daily_atari_total}回
              {item.daily_big_count != null && item.daily_reg_count != null && (
                <span className="font-normal text-helix-muted">
                  {" "}
                  (BB{item.daily_big_count}+RB{item.daily_reg_count})
                </span>
              )}
            </p>
          )}
          {item.week_diff_total != null && (
            <p className="mt-1 text-xs text-helix-muted">
              7日出玉 {formatWeekDiff(item.week_diff_total, kind)} · タップで詳細
            </p>
          )}
          <p className="mt-2 text-body">
            おすすめ度{" "}
            <span className={`font-bold ${tierClass}`}>{item.score}</span>
          </p>
          <ul className="mt-2 space-y-0.5">
            {item.reasons.slice(0, 3).map((r, i) => (
              <li key={i} className="text-meta text-helix-muted">
                {plainTextForGame(r, kind)}
              </li>
            ))}
          </ul>
          {item.expected_investment != null &&
            (item.tier === "recommend" || item.tier === "hold") && (
              <div className="mt-2 rounded-lg border border-helix-border/80 bg-black/20 px-2 py-2 text-meta">
                <p className="text-[10px] text-helix-muted">{rateLabel(kind)}</p>
                <p>
                  {MONEY_LABEL.bet}{" "}
                  <span className="font-bold text-helix-accent">
                    {formatBetYen(item.expected_investment, kind)}
                  </span>
                </p>
                {item.max_risk_line != null && (
                  <p className="text-helix-muted">
                    {MONEY_LABEL.stop}{" "}
                    <span className="font-semibold text-amber-200/90">
                      {formatBetYen(item.max_risk_line, kind)}
                    </span>
                  </p>
                )}
              </div>
            )}
        </div>
      </div>
    </Link>
  );
}
