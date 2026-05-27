"use client";

import { Suspense, useState, type ReactNode } from "react";
import { useDensity } from "@/lib/density";

type Props = {
  id: string;
  title: string;
  summary?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  lazyLoad?: boolean;
};

export function AccordionSection({
  id,
  title,
  summary,
  children,
  defaultOpen = false,
  lazyLoad = false,
}: Props) {
  const { isSimple } = useDensity();
  const [open, setOpen] = useState(defaultOpen);

  if (isSimple) {
    return null;
  }

  return (
    <section className="mx-4 mb-3 overflow-hidden rounded-xl border border-helix-border bg-helix-surface/60">
      <button
        type="button"
        id={`acc-${id}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
      >
        <div className="min-w-0">
          <p className="text-sm font-bold text-helix-text">{title}</p>
          {!open && summary && (
            <div className="mt-0.5 text-xs text-helix-muted">{summary}</div>
          )}
        </div>
        <span className="shrink-0 text-helix-muted">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="border-t border-helix-border/80 px-1 pb-2">
          {lazyLoad ? (
            <Suspense fallback={<p className="px-3 py-4 text-xs text-helix-muted">読込中…</p>}>
              {children}
            </Suspense>
          ) : (
            children
          )}
        </div>
      )}
    </section>
  );
}
