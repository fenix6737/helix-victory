"use client";

import { useId, useState, type ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  testId?: string;
  badge?: string;
};

export function CollapseSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
  testId,
  badge,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();

  return (
    <div className="border-t border-white/10 first:border-t-0" data-testid={testId}>
      <button
        type="button"
        className="flex min-h-tap w-full items-center justify-between gap-2 py-2.5 text-left"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
      >
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-amber-50">{title}</p>
          {subtitle && !open && (
            <p className="mt-0.5 truncate text-xs text-amber-100/70">{subtitle}</p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {badge && (
            <span className="rounded-full bg-black/30 px-2 py-0.5 text-[10px] text-amber-200/90">
              {badge}
            </span>
          )}
          <span className="text-lg leading-none text-amber-200/80" aria-hidden>
            {open ? "▲" : "▼"}
          </span>
        </div>
      </button>
      {open && (
        <div id={panelId} className="pb-3 text-sm leading-relaxed text-amber-50/95">
          {children}
        </div>
      )}
    </div>
  );
}
