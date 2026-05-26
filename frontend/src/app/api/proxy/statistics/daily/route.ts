import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { getInternalApiUrl } from "@/lib/serverApi";

const API = getInternalApiUrl();

export async function GET(request: NextRequest) {
  const storeId = request.nextUrl.searchParams.get("store_id");
  if (!storeId) return NextResponse.json({ detail: "store_id required" }, { status: 400 });
  const token = (await cookies()).get("helix_token")?.value;
  if (!token) return NextResponse.json({ detail: "unauthorized" }, { status: 401 });
  const res = await fetch(`${API}/api/v1/stores/${storeId}/statistics/daily`, {
    headers: { Authorization: `Bearer ${token}` },
    next: { revalidate: 60 },
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
