"use client";

import { useState } from "react";
import type { StoreLiveEv } from "@/lib/api";
import { CollapseSection } from "@/components/CollapseSection";
import {
  formatBetYen,
  formatDiffYen,
  MONEY_LABEL,
  rateLabel,
  type GameKind,
  unitLabel,
} from "@/lib/money";
import {
  modeHint,
  plainIsland,
  plainText,
} from "@/lib/plainJapanese";

type Props = {
  liveEv: StoreLiveEv | null;
  fetchError?: string | null;
  stale?: boolean;
  gameKind: GameKind;
};

const MODE_STYLE: Record<string, string> = {
  attack: "border-emerald-500/70 bg-gradient-to-b from-emerald-950/80 to-black/40",
  careful: "border-amber-500/70 bg-gradient-to-b from-amber-950/50 to-black/40",
  avoid: "border-red-500/80 bg-gradient-to-b from-red-950/60 to-black/40",
  retreat: "border-slate-400/70 bg-gradient-to-b from-slate-900/90 to-black/50",
};

const MODE_HEADLINE: Record<string, string> = {
  attack: "打ってよい",
  careful: "慎重に",
  avoid: "危ない",
  retreat: "やめる",
};

function Row({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <div className="min-w-0">
        <p className="text-xs text-amber-100/75">{label}</p>
        {hint && <p className="text-[10px] text-amber-100/50">{hint}</p>}
      </div>
      <p className="shrink-0 text-right text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function CombatPanel({ liveEv, fetchError, stale, gameKind }: Props) {
  const [showDetails, setShowDetails] = useState(false);
  const kindLabel = unitLabel(gameKind);
  const rateHint = rateLabel(gameKind);

  if (fetchError) {
    return (
      <div
        className="border-b border-red-500/40 bg-red-950/95 px-4 py-3 text-sm text-red-200"
        data-testid="combat-panel-error"
      >
        取得できませんでした: {fetchError}
      </div>
    );
  }

  if (!liveEv) {
    return (
      <div
        className="animate-pulse border-b border-helix-border bg-helix-surface px-4 py-4"
        data-testid="combat-panel-skeleton"
      >
        <div className="h-6 w-24 rounded bg-helix-border" />
        <div className="mt-2 h-4 w-full rounded bg-helix-border" />
      </div>
    );
  }

  const mode = liveEv.combat_mode?.mode ?? (liveEv.should_play ? "attack" : "retreat");
  const boxClass = MODE_STYLE[mode] ?? MODE_STYLE.retreat;
  const headline = MODE_HEADLINE[mode] ?? liveEv.combat_mode?.label ?? "—";
  const subline = plainText(liveEv.danger_headline);
  const hint = modeHint(mode);
  const isCritical = liveEv.danger_level === "critical";
  const isDefenseDay = (liveEv.danger_score ?? 0) >= 50;
  const q = liveEv.quantile;
  const evMain = liveEv.primary?.current_ev;
  const cacheNote =
    liveEv.cache_degraded || stale || liveEv.stale_warning
      ? plainText(
          liveEv.cache_degraded ? "degraded — メモリキャッシュ" : "更新中（キャッシュ）"
        )
      : null;

  const primaryLine = liveEv.primary
    ? `${liveEv.primary.machine_number}番 ${liveEv.primary.title.slice(0, 14)}`
    : "候補を探しています…";

  const altLine =
    liveEv.alternatives.length > 0
      ? liveEv.alternatives
          .map((a) => `${a.machine_number}番（期待${a.current_ev.toFixed(0)}）`)
          .join("、")
      : "";

  const retreatPlain = (liveEv.retreat_reason ?? []).map(plainText);
  const driftPlain = (liveEv.drift_alerts ?? []).map(plainText);

  const inv = liveEv.expected_investment ?? 0;
  const betSubtitle = inv > 0 ? formatBetYen(inv, gameKind) : undefined;

  return (
    <div
      className={`border-b-2 px-4 py-3 ${boxClass} ${
        isCritical ? "animate-pulse ring-2 ring-red-500" : ""
      }`}
      data-testid="combat-panel"
      data-combat-mode={mode}
    >
      <p className="mb-1 text-[10px] font-medium text-amber-200/70">{kindLabel} · {rateHint}</p>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-2xl font-black tracking-tight text-amber-50">{headline}</p>
          <p className="mt-0.5 text-sm leading-snug text-amber-100/90">{subline}</p>
          {hint && <p className="mt-1 text-xs text-amber-100/70">{hint}</p>}
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[10px] text-amber-100/60">期待指数</p>
          <p className="text-3xl font-black tabular-nums text-amber-400">
            {evMain != null ? evMain.toFixed(0) : "—"}
          </p>
          <p className="text-[10px] text-amber-100/50">高いほど狙い目</p>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-black/30 px-2.5 py-2">
          <p className="text-[10px] text-amber-100/60">{MONEY_LABEL.bet}</p>
          <p className="text-base font-bold tabular-nums text-emerald-300">
            {formatBetYen(liveEv.expected_investment, gameKind)}
          </p>
        </div>
        <div className="rounded-lg bg-black/30 px-2.5 py-2">
          <p className="text-[10px] text-amber-100/60">{MONEY_LABEL.stop}</p>
          <p className="text-base font-bold tabular-nums text-amber-200">
            {formatBetYen(liveEv.death_line, gameKind)}
          </p>
        </div>
      </div>

      <p className="mt-2 rounded-lg bg-black/25 px-3 py-2 text-sm font-medium text-amber-50">
        いち推し: {primaryLine}
        {liveEv.fake_release && (
          <span className="ml-1 text-xs text-amber-200/80">（見せかけ出玉に注意）</span>
        )}
        {liveEv.trap_wave && (
          <span className="ml-1 text-xs text-amber-200/80">（はまり波に注意）</span>
        )}
      </p>
      {isDefenseDay && (
        <p className="mt-2 rounded-lg border border-amber-400/60 bg-amber-950/40 px-3 py-2 text-xs font-semibold text-amber-100">
          危険度が高いため、今日は最上位1台以外は触らない運用を推奨します。
        </p>
      )}

      <button
        type="button"
        className="mt-2 flex min-h-tap w-full items-center justify-center gap-2 rounded-lg border border-amber-200/20 bg-black/20 py-2 text-sm font-semibold text-amber-100"
        onClick={() => setShowDetails((v) => !v)}
        aria-expanded={showDetails}
      >
        {showDetails ? "▲ 詳細をたたむ" : "▼ 詳細・数字を見る"}
      </button>

      {showDetails && (
        <div className="mt-2 rounded-xl bg-black/20 px-3">
          {cacheNote && (
            <CollapseSection title="データの状態" subtitle={cacheNote} defaultOpen>
              <p className="text-xs">{cacheNote}</p>
              {liveEv.data_freshness_sec != null && (
                <p className="mt-1 text-xs text-amber-100/70">
                  最終更新から約 {Math.round(liveEv.data_freshness_sec / 60)} 分前
                </p>
              )}
              <Row
                label="分析の確信度"
                hint="データ量に基づく信頼"
                value={`${((liveEv.confidence ?? 1) * 100).toFixed(0)}%`}
              />
            </CollapseSection>
          )}

          {!cacheNote && (
            <CollapseSection
              title="データの状態"
              subtitle={`確信度 ${((liveEv.confidence ?? 1) * 100).toFixed(0)}%`}
            >
              <Row
                label="分析の確信度"
                hint="データ量に基づく信頼"
                value={`${((liveEv.confidence ?? 1) * 100).toFixed(0)}%`}
              />
            </CollapseSection>
          )}

          <CollapseSection
            title={`${kindLabel}の金額目安`}
            subtitle={betSubtitle}
            defaultOpen={mode === "retreat" || mode === "avoid"}
          >
            <Row label={MONEY_LABEL.bet} hint={rateHint} value={formatBetYen(liveEv.expected_investment ?? 0, gameKind)} />
            <Row label={MONEY_LABEL.stop} hint="この金額感を超えたらやめどき" value={formatBetYen(liveEv.death_line ?? 0, gameKind)} />
            <Row
              label="最悪の想定（金額）"
              hint="うまくいかなかった場合"
              value={formatDiffYen(
                liveEv.worst_case_ev ?? q?.worst_case ?? null,
                gameKind
              )}
            />
            {q && (
              <>
                <Row label="まずまずの結果" value={formatDiffYen(q.median_ev, gameKind)} />
                <Row label="うまくいった場合" value={formatDiffYen(q.upside_ev, gameKind)} />
                <Row
                  label="微妙な場合"
                  value={formatDiffYen(q.downside_risk, gameKind)}
                />
              </>
            )}
          </CollapseSection>

          <CollapseSection title="おすすめ度・やめる度合い">
            <Row
              label="おすすめ度"
              hint="高いほど推奨に近い"
              value={liveEv.recommend_score?.toFixed(0) ?? "—"}
            />
            <Row
              label="やめる度合い"
              hint="高いほど撤退寄り"
              value={liveEv.retreat_score?.toFixed(0) ?? "—"}
            />
            <Row
              label="島が崩れる見込み"
              value={`${((liveEv.collapse_probability ?? 0) * 100).toFixed(0)}%`}
            />
            <Row label="島の様子" value={plainIsland(liveEv.island_state ?? "")} />
            {liveEv.recent_drift != null && liveEv.recent_drift > 0.3 && (
              <Row
                label="店の傾向の変化"
                hint="いつもと違う動き"
                value={`${(liveEv.recent_drift * 100).toFixed(0)}%`}
              />
            )}
          </CollapseSection>

          {(retreatPlain.length > 0 || driftPlain.length > 0) && (
            <CollapseSection
              title="やめる・注意の理由"
              subtitle={retreatPlain[0] ?? driftPlain[0]}
              defaultOpen={mode === "retreat"}
              testId="retreat-reason"
            >
              {retreatPlain.length > 0 && (
                <ul className="list-disc space-y-1 pl-4 text-xs">
                  {retreatPlain.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              )}
              {driftPlain.map((a, i) => (
                <p key={i} className="mt-2 text-xs text-amber-200/85">
                  {a}
                </p>
              ))}
            </CollapseSection>
          )}

          <CollapseSection
            title="次点の台"
            subtitle={altLine || "なし"}
            testId="alt-candidates"
          >
            {altLine ? (
              <p className="text-sm">{altLine}</p>
            ) : (
              <p className="text-xs text-amber-100/70">次点候補はありません</p>
            )}
          </CollapseSection>
        </div>
      )}

      {!showDetails && altLine && (
        <p className="mt-1 text-xs text-amber-100/70" data-testid="alt-candidates">
          次点: {altLine}
        </p>
      )}
    </div>
  );
}
