"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchWithGuard } from "@/lib/uiGuardian";

type Settings = { store_id: string; ev_mode: boolean; ev_mode_label: string };

type Props = { storeId: string };

export function EvModeToggle({ storeId }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const res = await fetchWithGuard<Settings>(
      `/api/proxy/analysis-settings?store_id=${storeId}`
    );
    if (res.ok) setSettings(res.data);
  }, [storeId]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async () => {
    if (!settings) return;
    setSaving(true);
    const next = !settings.ev_mode;
    const res = await fetchWithGuard<Settings>(
      `/api/proxy/analysis-settings?store_id=${storeId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ev_mode: next }),
      }
    );
    setSaving(false);
    if (res.ok) setSettings(res.data);
  };

  if (!settings) return null;

  return (
    <section className="mx-4 mb-3 rounded-xl border border-violet-500/35 bg-violet-950/25 p-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-violet-100">期待値重視モード</h2>
          <p className="mt-0.5 text-[11px] text-violet-200/80">
            ON: 凹み・角台・右肩波形を排除しボーダー・店舗クセで推奨
          </p>
        </div>
        <button
          type="button"
          disabled={saving}
          onClick={() => void toggle()}
          className={`shrink-0 rounded-full px-4 py-2 text-xs font-bold ${
            settings.ev_mode
              ? "bg-violet-600 text-white"
              : "bg-helix-border text-helix-muted"
          }`}
        >
          {settings.ev_mode ? "ON" : "OFF"}
        </button>
      </div>
      <p className="mt-2 text-[10px] text-helix-muted">{settings.ev_mode_label}</p>
    </section>
  );
}
