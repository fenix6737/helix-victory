import type { NextConfig } from "next";

const internalApi =
  process.env.API_URL_INTERNAL?.trim() || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Fly/Docker ビルド時のみ standalone（HELIX_STANDALONE=1）
  ...(process.env.HELIX_STANDALONE === "1" ? { output: "standalone" as const } : {}),
  // 単一ポート公開時: collector / 監視が /api/v1 へ到達できるよう内部 API へ転送
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${internalApi}/api/v1/:path*` },
      { source: "/health", destination: `${internalApi}/health` },
      { source: "/health/:path*", destination: `${internalApi}/health/:path*` },
    ];
  },
};

export default nextConfig;