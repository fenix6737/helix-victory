/** Next.js サーバー側からバックエンド API へ（常にローカル可） */
export function getInternalApiUrl(): string {
  const raw =
    process.env.API_URL_INTERNAL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}
