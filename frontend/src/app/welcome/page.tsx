import Link from "next/link";

import { PublicUrlBanner } from "@/components/PublicUrlBanner";

export default function WelcomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-center">
      <PublicUrlBanner />
      <h1 className="text-title">Helix Victory</h1>
      <p className="mt-3 text-body text-helix-muted">
        マルハン梅田店・キコーナ尼崎本店向け
        <br />
        高期待値抽出エンジン
      </p>
      <p className="mt-6 text-meta text-helix-muted">
        本サイトは常時公開しています。分析結果の閲覧は管理者のみ可能です。
      </p>
      <Link
        href="/login"
        className="mt-10 inline-block rounded-lg bg-helix-accent px-8 py-3 text-body font-medium text-white"
      >
        管理者ログイン
      </Link>
    </main>
  );
}
