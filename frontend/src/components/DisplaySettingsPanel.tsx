"use client";

import { useState } from "react";
import { useDensity, type DisplaySections } from "@/lib/density";

export function DisplaySettingsPanel() {
  const { sections, setSections } = useDensity();
  const [open, setOpen] = useState(false);

  function toggle(key: keyof DisplaySections) {
    setSections({ ...sections, [key]: !sections[key] });
  }

  return (
    <div className="relative px-4 pb-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-tap items-center gap-2 rounded-lg border border-helix-border bg-helix-surface px-3 py-2 text-xs font-semibold text-helix-muted"
        aria-label="表示設定"
      >
        <span aria-hidden>⚙</span> 表示設定
      </button>
      {open && (
        <div className="absolute left-4 right-4 top-full z-40 mt-1 rounded-xl border border-helix-border bg-helix-bg p-3 shadow-xl">
          <p className="mb-2 text-xs font-bold text-helix-muted">セクションの表示</p>
          {(
            [
              ["stats", "統計ダッシュボード"],
              ["accuracy", "推奨精度"],
              ["features", "店舗・実戦メモ"],
              ["combat", "実戦パネル"],
            ] as const
          ).map(([key, label]) => (
            <label
              key={key}
              className="flex min-h-tap cursor-pointer items-center gap-2 py-1.5 text-sm"
            >
              <input
                type="checkbox"
                checked={sections[key]}
                onChange={() => toggle(key)}
                className="h-4 w-4 rounded border-helix-border"
              />
              {label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
