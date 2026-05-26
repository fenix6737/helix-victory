"use client";

import { useEffect, useState } from "react";

type PublicUrlPayload = {
  available: boolean;
  welcome_url?: string | null;
  mode?: string | null;
  note?: string | null;
  updated_at?: string | null;
};

export function PublicUrlBanner() {
  const [data, setData] = useState<PublicUrlPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/public-url", { cache: "no-store" });
        if (!res.ok) return;
        const json = (await res.json()) as PublicUrlPayload;
        if (!cancelled) setData(json);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!data?.available || !data.welcome_url) return null;

  const isQuick = data.mode === "quick";

  return (
    <section className="mb-8 rounded-lg border border-helix-accent/40 bg-helix-accent/10 px-4 py-3 text-left">
      <p className="text-meta font-medium text-helix-accent">いまの公開URL</p>
      <a
        href={data.welcome_url}
        className="mt-2 block break-all text-body text-white underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {data.welcome_url}
      </a>
      {isQuick ? (
        <p className="mt-2 text-meta text-helix-muted">
          PC再起動のたびに変わります。最新はデスクトップの「Helix Victory (公開).url」または
          data/public-url.txt を確認してください。
        </p>
      ) : null}
    </section>
  );
}
