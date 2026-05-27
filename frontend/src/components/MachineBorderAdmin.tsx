"use client";

import { useCallback, useState } from "react";
import { AccordionSection } from "@/components/AccordionSection";

export function MachineBorderAdmin() {
  const [csv, setCsv] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onFile = useCallback((file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => setCsv(String(reader.result ?? ""));
    reader.readAsText(file, "UTF-8");
  }, []);

  async function importCsv() {
    if (!csv.trim()) {
      setMsg("CSVを入力またはファイルを選択してください");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const res = await fetch("/api/proxy/machine-borders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_text: csv, replace: false }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setMsg(body.detail || `インポート失敗 (${res.status})`);
        return;
      }
      setMsg(`登録 ${body.imported ?? 0}件 / 更新 ${body.updated ?? 0}件`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "通信エラー");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AccordionSection
      id="border-admin"
      title="ボーダーマスタ CSV"
      summary="機種別等価ボーダーの手動インポート"
      defaultOpen={false}
    >
      <div className="space-y-2 px-3 py-2">
        <p className="text-[10px] text-helix-muted">
          列: title_pattern, border_per_1000_yen [, game_type, coin_price_yen, base_games]
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          className="block w-full text-xs"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        <textarea
          value={csv}
          onChange={(e) => setCsv(e.target.value)}
          rows={4}
          placeholder="title_pattern,border_per_1000_yen&#10;Pエヴァンゲリオン,16.5,pachinko,4,400"
          className="w-full rounded-lg border border-helix-border bg-black/30 p-2 text-xs"
        />
        <button
          type="button"
          disabled={busy}
          onClick={() => void importCsv()}
          className="w-full rounded-lg bg-helix-accent py-2 text-sm font-bold text-white disabled:opacity-50"
        >
          {busy ? "送信中…" : "CSVインポート"}
        </button>
        {msg && <p className="text-xs text-amber-200">{msg}</p>}
      </div>
    </AccordionSection>
  );
}
