import { NextResponse } from "next/server";

import { getInternalApiUrl } from "@/lib/serverApi";

export async function GET() {
  const res = await fetch(`${getInternalApiUrl()}/api/v1/system/public-url`, {
    cache: "no-store",
  });
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: { "Content-Type": "application/json" },
  });
}
