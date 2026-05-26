"use client";

type Props = {
  offline: boolean;
  isStale: boolean;
  noData: boolean;
  lastIngest?: string | null;
  lastAnalysis?: string | null;
  generatedAt?: string;
  pollingSec: number;
};

export function LiveActivityBar({
  offline,
  isStale,
  noData,
  lastIngest,
  lastAnalysis,
  generatedAt,
  pollingSec,
}: Props) {
  const active = !offline && !noData && !isStale;

  return (
    <div className="mx-4 mb-2 flex items-center gap-3 rounded-lg border border-helix-border/80 bg-black/30 px-3 py-2">
      <span
        className={`relative flex h-3 w-3 shrink-0 rounded-full ${
          active ? "bg-emerald-400" : isStale ? "bg-amber-400" : "bg-slate-500"
        }`}
      >
        {active && (
          <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/60" />
        )}
      </span>
      <div className="min-w-0 flex-1 text-xs leading-snug">
        <p className="font-semibold text-amber-50">
          {offline
            ? "オフライン — 保存データ"
            : noData
              ? "データ準備中"
              : isStale
                ? "分析を更新しています…"
                : "リアルタイム分析中"}
        </p>
        {!offline && !noData && (
          <p className="text-helix-muted">
            {lastIngest && `収集 ${lastIngest}`}
            {lastAnalysis && ` · 分析 ${lastAnalysis}`}
            {generatedAt && ` · 一覧 ${generatedAt}`}
            {` · ${pollingSec}秒ごと`}
          </p>
        )}
      </div>
    </div>
  );
}
