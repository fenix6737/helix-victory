"use client";

import type { Store } from "@/lib/api";

type Props = {
  stores: Store[];
  current: string;
  onChange: (id: string) => void;
};

export function StoreSwitcher({ stores, current, onChange }: Props) {
  return (
    <div className="flex gap-2 p-3">
      {stores.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onChange(s.id)}
          className={`min-h-tap flex-1 rounded-lg px-3 py-3 text-body font-semibold transition-colors ${
            current === s.id
              ? "bg-helix-accent text-white"
              : "bg-helix-surface text-helix-muted border border-helix-border"
          }`}
        >
          {s.name.replace("マルハン", "M").replace("キコーナ", "K")}
        </button>
      ))}
    </div>
  );
}
