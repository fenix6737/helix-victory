"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "ログインに失敗しました");
        return;
      }
      const from = params.get("from") || "/";
      router.replace(from);
      router.refresh();
    } catch {
      setError("サーバーに接続できません");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6">
      <h1 className="text-title">Helix Victory</h1>
      <p className="mt-2 text-meta text-helix-muted">管理者ログイン</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <div>
          <label className="text-meta text-helix-muted">管理者ID</label>
          <input
            type="text"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="mt-1 w-full rounded-lg border border-helix-border bg-helix-surface px-4 py-3 text-body"
            required
          />
        </div>
        <div>
          <label className="text-meta text-helix-muted">パスワード</label>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded-lg border border-helix-border bg-helix-surface px-4 py-3 text-body"
            required
          />
        </div>
        {error && <p className="text-meta text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="min-h-tap w-full rounded-lg bg-helix-accent py-3 text-body font-semibold text-white disabled:opacity-50"
        >
          {loading ? "認証中…" : "ログイン"}
        </button>
      </form>
    </main>
  );
}
