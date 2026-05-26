export const PREF_STORE_KEY = "helix_store_id";
export const PREF_GAME_KEY = "helix_game_kind";

export type GameKindPref = "slot" | "pachinko";

export function loadStorePreference(fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return localStorage.getItem(PREF_STORE_KEY) || fallback;
}

export function saveStorePreference(storeId: string) {
  localStorage.setItem(PREF_STORE_KEY, storeId);
}

export function loadGamePreference(fallback: GameKindPref): GameKindPref {
  if (typeof window === "undefined") return fallback;
  const v = localStorage.getItem(PREF_GAME_KEY);
  return v === "pachinko" ? "pachinko" : "slot";
}

export function saveGamePreference(kind: GameKindPref) {
  localStorage.setItem(PREF_GAME_KEY, kind);
}
