/** 専門用語を素人向けの日本語にそろえる */

const EXACT: Record<string, string> = {
  "degraded — メモリキャッシュ": "簡易表示モード（サーバー負荷軽減中）",
  "更新中（キャッシュ）": "データ更新中…",
  "通常営業想定 — 推奨台を優先": "いつも通りの営業 — 推奨台から選ぶ",
  "要注意 — 厳選台のみ": "少し注意 — 厳選した台だけ",
  "危険 — 打たない最適": "危ない日 — 打たないのが正解",
  "critical — 本日は行かない": "とても危険 — 今日は行かない",
  "今日は危険 — 打たない判断も最適": "今日は危ない — 打たない判断が正解",
  "データ不足 — 本日は様子見推奨": "データが足りない — 今日は見送り推奨",
  "配置/平均差枚の急変": "台の配置や平均差枚が急に変わっています",
  "稼働導線変化": "客の流れ・稼働の仕方が変わっています",
  "島構成変更 — 強島入替": "島の入れ替えがありました",
  "放出位置変更": "出玉の出やすい位置が変わった可能性",
  "角優遇消失の疑い": "角台の優遇が弱まった可能性",
  "特徴量ドリフト検出": "店の傾向がいつもと違う可能性",
  "島崩壊検知": "島全体が弱くなっています",
  "drift急変": "店の傾向が急に変わっています",
  "death_line超過": "想定よりハマり深い計算です",
  "danger critical": "危険度が最高です",
  "EV低下": "期待値が下がっています",
  "偽放出": "見せかけの出玉の疑い",
  "罠波": "はまりやすい波の疑い",
  "深ハマリ": "深くハマるリスク",
  "監視": "要ウォッチ",
};

const ISLAND: Record<string, string> = {
  active: "島は稼働中",
  cooling: "島は冷え気味",
  collapsed: "島は崩れ気味",
  unknown: "島の状態不明",
};

const MODE_HINT: Record<string, string> = {
  attack: "このまま推奨台を中心に打てます",
  careful: "無理せず、条件の良い台だけに絞りましょう",
  avoid: "危険が高い — 打つなら厳選のみ",
  retreat: "いったんやめる・別の台を検討",
};

const PREFIX: [RegExp, string][] = [
  [/^特定日一致/, "過去と同じ日付の動きに似ています"],
  [/^一撃型波形/, "一気に出るタイプの波形"],
  [/^右肩型波形/, "右肩上がりの波形"],
  [/^放出型波形/, "出玉が出やすい波形"],
  [/^死亡型波形/, "沈みやすい波形"],
  [/^設定型波形/, "設定示唆のある波形"],
  [/^事故\/罠波形/, "事故・罠っぽい波形"],
  [/^サンプル不足/, "過去データが少ない"],
  [/^データ欠損/, "データに欠けがある"],
  [/^稼働不足/, "回転・稼働が足りない"],
  [/^店舗死に位置/, "店で負けやすい位置"],
  [/^回収周期一致/, "回収の周期と一致"],
  [/^据え置き低設定/, "据え置きで低めの設定疑い"],
  [/^長期未投入島/, "長く傾向固定の島"],
  [/^角2配置/, "角2の位置"],
  [/^角配置/, "角台の位置"],
  [/^島全体強化/, "島全体が強め"],
  [/^店舗放出モード/, "店が出玉モード"],
  [/^過去同条件投入/, "同じ条件で過去に打たれやすい"],
  [/^店舗営業パターン/, "この店のいつもの動きから期待"],
  [/^要確認/, "もう少し様子見"],
  [/^低期待値/, "期待は低め"],
  [/^期待値消化/, "もう出し切った可能性"],
  [/^営業ドリフト/, "店の傾向が変わった"],
  [/^凹み後/, "凹んだあとの反発期待"],
];

export function plainText(text: string): string {
  const raw = text.trim();
  if (EXACT[raw]) return EXACT[raw];
  const t = raw.replace(/^・+/, "");
  if (EXACT[t]) return EXACT[t];
  if (/崩壊確率/.test(t)) {
    return t.replace("崩壊確率", "島が崩れる見込み");
  }
  for (const [re, msg] of PREFIX) {
    if (re.test(t)) return msg;
  }
  return raw.startsWith("・") ? t : raw;
}

function normalizeUnitForGame(
  text: string,
  gameType?: "slot" | "pachinko" | string | null
): string {
  if (gameType !== "pachinko") return text;
  return text.replace(/([+\-−]?\d[\d,]*)枚/g, "$1玉");
}

export function plainTextForGame(
  text: string,
  gameType?: "slot" | "pachinko" | string | null
): string {
  return normalizeUnitForGame(plainText(text), gameType);
}

export function plainIsland(state: string | undefined): string {
  if (!state) return "—";
  return ISLAND[state] ?? `島: ${state}`;
}

export function modeHint(mode: string): string {
  return MODE_HINT[mode] ?? "";
}

export function plainPosition(pos: string | null | undefined): string {
  if (!pos) return "配置不明";
  const map: Record<string, string> = {
    corner: "角台",
    corner2: "角2（端）",
    main_aisle: "通路側",
    row: "島の中段",
  };
  return map[pos] ?? pos;
}

export function plainIslandShort(island: string | null | undefined): string {
  if (!island) return "島未設定";
  const s = island.replace(/^island_/i, "").replace(/_/g, " ");
  return `島 ${s}`;
}

const WF_SHORT: Record<string, string> = {
  right_shoulder: "右肩上がり",
  v_shape: "V字回復",
  one_shot: "一撃型",
  release: "放出型",
  death: "沈み型",
};

/** カード1行 — なぜ推奨か */
export function formatWhyLine(
  reasons: string[],
  positionType: string | null | undefined,
  waveform: string | null | undefined,
  gameType?: "slot" | "pachinko" | string | null
): string {
  const skip = /不足|欠損|稼働不足|低期待値/;
  const hit = reasons
    .map((r) => plainTextForGame(r, gameType))
    .find((r) => r && !skip.test(r));
  if (hit) return hit;
  const parts: string[] = [];
  const pos = plainPosition(positionType);
  if (pos !== "配置不明") parts.push(pos);
  if (waveform && WF_SHORT[waveform]) parts.push(WF_SHORT[waveform]);
  return parts.length ? parts.join(" · ") : "過去データから期待が高い台";
}
