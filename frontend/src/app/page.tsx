import { redirect } from "next/navigation";
import { HomeClient } from "./HomeClient";
import { fetchStores, fetchTodayRecommendations } from "@/lib/api";

const DEFAULT_STORE = "kicona_amagasaki";

export default async function HomePage() {
  try {
    const stores = await fetchStores();
    const recommendations = await fetchTodayRecommendations(DEFAULT_STORE, "slot");
    return (
      <HomeClient
        initialStores={stores}
        initialStoreId={DEFAULT_STORE}
        initialRecommendations={recommendations}
      />
    );
  } catch (e) {
    if (e instanceof Error && e.message === "UNAUTHORIZED") {
      redirect("/login");
    }
    return (
      <main className="px-4 py-12 text-center">
        <p className="text-body">APIに接続できません</p>
        <p className="mt-2 text-meta text-helix-muted">
          バックエンド起動後、データ収集・分析を実行してください
        </p>
      </main>
    );
  }
}
