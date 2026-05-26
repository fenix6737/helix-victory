import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const API = process.env.HELIX_API_INTERNAL_URL || "http://127.0.0.1:8000";

export async function GET(req: NextRequest) {
  const storeId = req.nextUrl.searchParams.get("store_id");
  if (!storeId) {
    return NextResponse.json({ detail: "store_id required" }, { status: 400 });
  }
  const token = (await cookies()).get("helix_token")?.value;
  if (!token) return NextResponse.json({ detail: "unauthorized" }, { status: 401 });

  const res = await fetch(`${API}/api/v1/stores/${storeId}/analysis-settings`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}

export async function PATCH(req: NextRequest) {
  const storeId = req.nextUrl.searchParams.get("store_id");
  if (!storeId) {
    return NextResponse.json({ detail: "store_id required" }, { status: 400 });
  }
  const token = (await cookies()).get("helix_token")?.value;
  if (!token) return NextResponse.json({ detail: "unauthorized" }, { status: 401 });

  const payload = await req.text();
  const res = await fetch(`${API}/api/v1/stores/${storeId}/analysis-settings`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: payload,
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { "Content-Type": "application/json" } });
}
