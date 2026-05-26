"use client";

import type { TimeSeriesPoint } from "@/lib/api";

type Props = {
  points: TimeSeriesPoint[];
  field: "diff_coins" | "rotation_count";
  label: string;
};

export function MiniChart({ points, field, label }: Props) {
  const values = points
    .map((p) => p[field])
    .filter((v): v is number => v !== null && v !== undefined);

  if (values.length < 2) {
    return (
      <div className="rounded-lg bg-helix-surface p-4">
        <p className="text-meta text-helix-muted">{label}</p>
        <p className="mt-2 text-meta">データ不足</p>
      </div>
    );
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 280;
  const h = 64;
  const step = w / (values.length - 1);

  const path = values
    .map((v, i) => {
      const x = i * step;
      const y = h - ((v - min) / range) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  const last = values[values.length - 1];

  return (
    <div className="rounded-lg bg-helix-surface p-4">
      <div className="flex items-baseline justify-between">
        <p className="text-meta text-helix-muted">{label}</p>
        <p className="text-body font-semibold">{last.toLocaleString()}</p>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 w-full" aria-hidden>
        <path d={path} fill="none" stroke="#3b82f6" strokeWidth="2" />
      </svg>
    </div>
  );
}
