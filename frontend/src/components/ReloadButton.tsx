"use client";

type Props = {
  onReload: () => void;
  loading?: boolean;
  disabled?: boolean;
};

export function ReloadButton({ onReload, loading, disabled }: Props) {
  return (
    <button
      type="button"
      onClick={onReload}
      disabled={disabled || loading}
      aria-label="最新データに更新"
      className="min-h-tap flex items-center gap-1.5 rounded-lg border border-helix-border bg-helix-surface px-3 py-2 text-xs font-bold text-helix-text transition active:scale-95 disabled:opacity-50"
    >
      <span
        className={`inline-block text-base leading-none ${loading ? "animate-spin" : ""}`}
        aria-hidden
      >
        ↻
      </span>
      {loading ? "更新中…" : "更新"}
    </button>
  );
}
