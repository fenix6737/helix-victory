import type { RecommendationItem } from "@/lib/api";
import { filterByBudget } from "@/lib/money";

/** 予算フィルタ後に台番号順・連番ランク */
export function applyBudgetAndRank(
  items: RecommendationItem[],
  budgetYen: number
): RecommendationItem[] {
  const filtered = filterByBudget(items, budgetYen);
  return filtered
    .sort((a, b) => a.machine_number - b.machine_number)
    .map((item, i) => ({ ...item, rank: i + 1 }));
}
