/** Wi-Fi なしでも前回データを即表示（localStorage） */

const PREFIX = "helix_v2:";
const DEFAULT_TTL_MS = 6 * 60 * 60 * 1000;

type Entry<T> = { savedAt: number; data: T };

function storageKey(key: string): string {
  return `${PREFIX}${key}`;
}

export function cacheRead<T>(key: string, ttlMs = DEFAULT_TTL_MS): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(storageKey(key));
    if (!raw) return null;
    const entry = JSON.parse(raw) as Entry<T>;
    if (Date.now() - entry.savedAt > ttlMs) {
      localStorage.removeItem(storageKey(key));
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export function cacheWrite<T>(key: string, data: T): void {
  if (typeof window === "undefined") return;
  try {
    const entry: Entry<T> = { savedAt: Date.now(), data };
    localStorage.setItem(storageKey(key), JSON.stringify(entry));
  } catch {
    /* quota */
  }
}

export function cacheSavedAt(key: string): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(storageKey(key));
    if (!raw) return null;
    return (JSON.parse(raw) as Entry<unknown>).savedAt;
  } catch {
    return null;
  }
}

export function apiCacheKey(path: string): string {
  return `api:${path}`;
}
