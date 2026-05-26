import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { getInternalApiUrl } from "@/lib/serverApi";

const API = getInternalApiUrl();

export async function POST(request: Request) {
  const body = await request.json();
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: "認証失敗" }));
    return NextResponse.json(detail, { status: res.status });
  }

  const data = await res.json();
  const cookieStore = await cookies();
  cookieStore.set("helix_token", data.access_token, {
    httpOnly: true,
    secure:
      process.env.HELIX_COOKIE_SECURE === "1" || process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: (data.expires_hours ?? 24) * 3600,
  });

  return NextResponse.json({ ok: true });
}
