import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { getInternalApiUrl } from "@/lib/serverApi";

const API = getInternalApiUrl();

export async function DELETE(
  _request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  const { id } = await context.params;
  const token = (await cookies()).get("helix_token")?.value;
  if (!token) return NextResponse.json({ detail: "unauthorized" }, { status: 401 });
  const res = await fetch(`${API}/api/v1/play-records/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  return new NextResponse(await res.text(), {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
