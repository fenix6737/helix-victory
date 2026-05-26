import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { getInternalApiUrl } from "@/lib/serverApi";

const API = getInternalApiUrl();

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  const { id } = await context.params;
  const token = (await cookies()).get("helix_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "unauthorized" }, { status: 401 });
  }
  const res = await fetch(`${API}/api/v1/machines/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
    next: { revalidate: 60 },
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
