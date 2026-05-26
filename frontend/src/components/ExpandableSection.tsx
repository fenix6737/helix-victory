"use client";

import { useState } from "react";

type Props = {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
};

export function ExpandableSection({ title, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-helix-border">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex min-h-tap w-full items-center justify-between px-4 py-4 text-left text-body font-semibold"
      >
        {title}
        <span className="text-helix-muted">{open ? "−" : "+"}</span>
      </button>
      {open && <div className="space-y-3 px-4 pb-4">{children}</div>}
    </div>
  );
}
