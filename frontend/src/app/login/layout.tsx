import { Suspense } from "react";

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<main className="p-8 text-center">読み込み中…</main>}>{children}</Suspense>;
}
