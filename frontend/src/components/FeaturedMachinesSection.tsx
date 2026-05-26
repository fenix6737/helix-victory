"use client";

import { RecommendationCard } from "@/components/RecommendationCard";
import type { RecommendationItem } from "@/lib/api";

type Props = {
  items: RecommendationItem[];
};

export function FeaturedMachinesSection({ items }: Props) {
  const featured = items.filter((i) => i.is_featured);
  if (featured.length === 0) return null;

  const ghoul = featured.filter((i) => i.featured_group === "tokyo_ghoul");
  const eva = featured.filter((i) => i.featured_group === "evangelion");

  return (
    <section className="mx-4 mt-4 rounded-xl border-2 border-amber-500/40 bg-gradient-to-b from-amber-950/40 to-helix-card/60 p-4">
      <h2 className="text-title text-amber-200">注目機種（喰種・エヴァ）</h2>
      <p className="mt-1 text-meta text-helix-muted">
        東京喰種シリーズ・エヴァンゲリオンシリーズを優先表示
      </p>
      {ghoul.length > 0 && (
        <div className="mt-3">
          <h3 className="mb-2 text-sm font-bold text-rose-300">東京喰種</h3>
          {ghoul.map((item) => (
            <RecommendationCard key={item.machine_id} item={item} pulse />
          ))}
        </div>
      )}
      {eva.length > 0 && (
        <div className="mt-3">
          <h3 className="mb-2 text-sm font-bold text-purple-300">エヴァンゲリオン</h3>
          {eva.map((item) => (
            <RecommendationCard key={item.machine_id} item={item} pulse />
          ))}
        </div>
      )}
    </section>
  );
}
