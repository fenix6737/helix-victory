/** UI安定化 — timeout / retry / stale / empty / オフライン */

import { cacheRead, cacheWrite } from "@/lib/offlineCache";

export type FetchResult<T> =
  | { ok: true; data: T; stale?: boolean; fromCache?: boolean }
  | { ok: false; error: string; offline?: boolean };

const DEFAULT_TIMEOUT_MS = 12_000;
export const LIVE_EV_TIMEOUT_MS = 35_000;
const MAX_RETRIES = 2;

export async function fetchWithGuard<T>(
  url: string,
  init?: RequestInit,
  opts?: {
    timeoutMs?: number;
    retries?: number;
    cacheKey?: string;
    cacheTtlMs?: number;
  }
): Promise<FetchResult<T>> {
  const online = typeof navigator !== "undefined" ? navigator.onLine : true;
  const timeoutMs = opts?.timeoutMs ?? (online ? DEFAULT_TIMEOUT_MS : 4_000);
  const retries = opts?.retries ?? (online ? MAX_RETRIES : 0);
  const storageKey = opts?.cacheKey;

  if (storageKey) {
    const cached = cacheRead<T>(storageKey, opts?.cacheTtlMs);
    if (cached != null && !online) {
      return { ok: true, data: cached, stale: true, fromCache: true };
    }
  }
  let lastErr = "unknown";

  const outerSignal = init?.signal;

  for (let attempt = 0; attempt <= retries; attempt++) {
    if (outerSignal?.aborted) {
      return { ok: false, error: "aborted" };
    }
    const ac = new AbortController();
    const onOuterAbort = () => ac.abort();
    outerSignal?.addEventListener("abort", onOuterAbort);
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...init, signal: ac.signal });
      clearTimeout(timer);
      outerSignal?.removeEventListener("abort", onOuterAbort);
      if (res.status === 401) {
        return { ok: false, error: "unauthorized" };
      }
      if (!res.ok) {
        lastErr = `HTTP ${res.status}`;
        if (attempt < retries) continue;
        return { ok: false, error: lastErr };
      }
      const data = (await res.json()) as T;
      if (storageKey) cacheWrite(storageKey, data);
      return { ok: true, data };
    } catch (e) {
      clearTimeout(timer);
      outerSignal?.removeEventListener("abort", onOuterAbort);
      if (outerSignal?.aborted) {
        return { ok: false, error: "aborted" };
      }
      const err = e as Error;
      if (err.name === "AbortError") lastErr = "timeout";
      else if (!navigator.onLine) lastErr = "offline";
      else lastErr = err.message || "network";
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 400 * (attempt + 1)));
        continue;
      }
      if (storageKey) {
        const cached = cacheRead<T>(storageKey, opts?.cacheTtlMs);
        if (cached != null) {
          return { ok: true, data: cached, stale: true, fromCache: true };
        }
      }
      return { ok: false, error: lastErr, offline: lastErr === "offline" || !online };
    }
  }
  if (storageKey) {
    const cached = cacheRead<T>(storageKey, opts?.cacheTtlMs);
    if (cached != null) {
      return { ok: true, data: cached, stale: true, fromCache: true };
    }
  }
  return { ok: false, error: lastErr, offline: !online };
}
