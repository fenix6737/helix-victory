/** 枚・玉 → 円表示（店舗レートは .env で調整可） */

import type { RecommendationItem } from "@/lib/api";

export type GameKind = "slot" | "pachinko";

const SLOT_YEN_PER_MEDAL =
  Number(process.env.NEXT_PUBLIC_SLOT_YEN_PER_MEDAL) || 20;
const PACHI_YEN_PER_UNIT =
  Number(process.env.NEXT_PUBLIC_PACHINKO_YEN_PER_BALL) || 4;

export const BUDGET_MAX_YEN = 50_000;

export const MONEY_LABEL = {
  bet: "賭けてよい目安",
  stop: "やめ時目安",
} as const;

export function unitLabel(kind: GameKind): string {
  return kind === "pachinko" ? "パチンコ" : "スロット";
}

export function rateLabel(kind: GameKind): string {
  return kind === "pachinko"
    ? `1玉≈${PACHI_YEN_PER_UNIT}円換算`
    : `1枚≈${SLOT_YEN_PER_MEDAL}円換算`;
}

export function coinsToYen(coins: number, kind: GameKind): number {
  const rate = kind === "pachinko" ? PACHI_YEN_PER_UNIT : SLOT_YEN_PER_MEDAL;
  return Math.round(coins * rate);
}

export function formatBetYen(
  coins: number | null | undefined,
  kind: GameKind
): string {
  if (coins == null || Number.isNaN(coins) || coins <= 0) return "—";
  return formatYen(coinsToYen(coins, kind));
}

export function formatDiffYen(
  coins: number | null | undefined,
  kind: GameKind
): string {
  if (coins == null || Number.isNaN(coins)) return "—";
  const yen = coinsToYen(Math.abs(coins), kind);
  const sign = coins < 0 ? "−" : "+";
  return `${sign}${formatYen(yen)}`;
}

export function formatWeekDiff(
  coins: number | null | undefined,
  kind: GameKind
): string {
  if (coins == null) return "—";
  return formatDiffYen(coins, kind);
}

export function formatYen(yen: number): string {
  const y = Math.round(yen);
  if (y >= 10000) {
    const man = y / 10000;
    return man >= 10 ? `約${Math.round(man)}万円` : `約${man.toFixed(1)}万円`;
  }
  return `¥${y.toLocaleString("ja-JP")}`;
}

export function itemBetYen(item: RecommendationItem): number {
  const kind = item.game_type === "pachinko" ? "pachinko" : "slot";
  return coinsToYen(item.expected_investment ?? 0, kind);
}

export function filterByBudget(
  items: RecommendationItem[],
  budgetYen: number
): RecommendationItem[] {
  if (budgetYen >= BUDGET_MAX_YEN) return items;
  return items.filter((item) => {
    const bet = item.expected_investment ?? 0;
    if (bet <= 0) return true;
    return itemBetYen(item) <= budgetYen;
  });
}
