"use client";

import { useDensity, type DensityMode } from "@/lib/density";

const MODES: { id: DensityMode; label: string }[] = [
  { id: "simple", label: "シンプル" },
  { id: "standard", label: "標準" },
  { id: "detailed", label: "詳細" },
];

export function DensityToggle() {
  const { mode, setMode } = useDensity();

  return (
    <div className="flex items-center gap-1 px-4 py-2">
      <span className="mr-1 text-[10px] font-medium text-helix-muted">表示</span>
      {MODES.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => setMode(m.id)}
          className={`min-h-tap rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition ${
            mode === m.id
              ? "bg-helix-accent text-white"
              : "bg-helix-surface text-helix-muted ring-1 ring-helix-border"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
