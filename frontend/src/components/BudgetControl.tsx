"use client";

import { BUDGET_MAX_YEN, formatYen } from "@/lib/money";

type Props = {
  budgetYen: number;
  onChange: (yen: number) => void;
};

export function BudgetControl({ budgetYen, onChange }: Props) {
  return (
    <div className="border-t border-helix-border px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-helix-accent">今日の予算</p>
        <p className="text-sm font-bold tabular-nums text-amber-300">
          {budgetYen >= BUDGET_MAX_YEN ? "上限なし" : formatYen(budgetYen)}
        </p>
      </div>
      <input
        type="range"
        min={0}
        max={BUDGET_MAX_YEN}
        step={1000}
        value={budgetYen}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-amber-500"
        aria-label="予算"
      />
      <div className="mt-1 flex justify-between text-[10px] text-helix-muted">
        <span>¥0</span>
        <span>¥5万</span>
      </div>
      <p className="mt-1 text-[10px] text-helix-muted">
        賭けてよい目安が予算内の台だけ表示（推奨・保留）
      </p>
    </div>
  );
}
