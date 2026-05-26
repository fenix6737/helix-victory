/** 推奨更新のブラウザ通知（PWA） */

export async function ensureNotifyPermission(): Promise<boolean> {
  if (typeof window === "undefined" || !("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  const p = await Notification.requestPermission();
  return p === "granted";
}

export function notifyRecommendationUpdate(
  storeName: string,
  recommendCount: number,
  topMachine?: number
) {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  if (document.visibilityState === "visible") return;

  const body =
    recommendCount > 0 && topMachine
      ? `推奨${recommendCount}台 — 1位は${topMachine}番`
      : `推奨リストを更新しました（${recommendCount}台）`;

  try {
    new Notification(`Helix — ${storeName}`, {
      body,
      tag: "helix-rec-update",
      icon: "/favicon.ico",
    });
  } catch {
    /* ignore */
  }
}
