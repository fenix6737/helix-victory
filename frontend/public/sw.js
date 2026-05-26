/* Helix Victory — オフライン向け軽量キャッシュ */
const STATIC = "helix-static-v1";
const API = "helix-api-v1";

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(STATIC));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => k !== STATIC && k !== API).map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/proxy/")) {
    event.respondWith(networkFirstApi(request));
    return;
  }

  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname === "/favicon.ico" ||
    url.pathname.endsWith(".css")
  ) {
    event.respondWith(cacheFirstStatic(request));
  }
});

async function networkFirstApi(request) {
  const cache = await caches.open(API);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ detail: "offline" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function cacheFirstStatic(request) {
  const cache = await caches.open(STATIC);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}
