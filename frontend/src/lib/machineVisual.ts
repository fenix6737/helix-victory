/** 台タイトルから一意のアイコン表現を生成 */

export function hashHue(title: string): number {
  let h = 0;
  for (let i = 0; i < title.length; i++) {
    h = (h * 31 + title.charCodeAt(i)) >>> 0;
  }
  return h % 360;
}

export function machineInitials(title: string): string {
  const t = title.trim();
  if (!t) return "?";
  if (t.startsWith("スマスロ")) return "スマ";
  if (t.startsWith("Lパチスロ") || t.startsWith("Lスマ")) return "L";
  if (t.startsWith("L") && t.length > 1) return "L";
  if (t.startsWith("パチスロ")) return "パス";
  if (t.includes("ジャグラー") || t.includes("Juggler")) return "J";
  if (t.startsWith("CR") || t.includes("パチンコ")) return "CR";
  if (t.startsWith("P")) return "P";
  const m = t.match(/[\u3040-\u9fff\u4e00-\u9fff]/);
  if (m) return m[0];
  return t.slice(0, 2);
}

export function iconStyleFromTitle(title: string, gameType: "slot" | "pachinko") {
  const hue = hashHue(title);
  const sat = gameType === "pachinko" ? 65 : 55;
  const light = gameType === "pachinko" ? 42 : 38;
  return {
    background: `linear-gradient(135deg, hsl(${hue} ${sat}% ${light}%) 0%, hsl(${(hue + 40) % 360} ${sat + 10}% ${light - 8}%) 100%)`,
    boxShadow: `0 0 14px hsla(${hue}, 80%, 50%, 0.35)`,
  };
}
