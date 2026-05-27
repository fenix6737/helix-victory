"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type DensityMode = "simple" | "standard" | "detailed";

export type DisplaySections = {
  stats: boolean;
  accuracy: boolean;
  features: boolean;
  combat: boolean;
};

const DENSITY_KEY = "helix_density_mode";
const SECTIONS_KEY = "helix_display_sections";

const DEFAULT_SECTIONS: DisplaySections = {
  stats: true,
  accuracy: true,
  features: true,
  combat: true,
};

type DensityContextValue = {
  mode: DensityMode;
  setMode: (m: DensityMode) => void;
  sections: DisplaySections;
  setSections: (s: DisplaySections) => void;
  densityClass: string;
  isSimple: boolean;
  isDetailed: boolean;
};

const DensityContext = createContext<DensityContextValue | null>(null);

function readMode(): DensityMode {
  if (typeof window === "undefined") return "standard";
  const v = localStorage.getItem(DENSITY_KEY);
  if (v === "simple" || v === "detailed") return v;
  return "standard";
}

function readSections(): DisplaySections {
  if (typeof window === "undefined") return DEFAULT_SECTIONS;
  try {
    const raw = localStorage.getItem(SECTIONS_KEY);
    if (!raw) return DEFAULT_SECTIONS;
    return { ...DEFAULT_SECTIONS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SECTIONS;
  }
}

export function DensityProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<DensityMode>("standard");
  const [sections, setSectionsState] = useState<DisplaySections>(DEFAULT_SECTIONS);

  useEffect(() => {
    setModeState(readMode());
    setSectionsState(readSections());
  }, []);

  const setMode = useCallback((m: DensityMode) => {
    setModeState(m);
    localStorage.setItem(DENSITY_KEY, m);
  }, []);

  const setSections = useCallback((s: DisplaySections) => {
    setSectionsState(s);
    localStorage.setItem(SECTIONS_KEY, JSON.stringify(s));
  }, []);

  const value = useMemo(
    () => ({
      mode,
      setMode,
      sections,
      setSections,
      densityClass: `is-${mode}`,
      isSimple: mode === "simple",
      isDetailed: mode === "detailed",
    }),
    [mode, sections, setMode, setSections]
  );

  return (
    <DensityContext.Provider value={value}>{children}</DensityContext.Provider>
  );
}

export function useDensity() {
  const ctx = useContext(DensityContext);
  if (!ctx) {
    throw new Error("useDensity must be used within DensityProvider");
  }
  return ctx;
}
