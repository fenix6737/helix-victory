import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC = [
  "/welcome",
  "/login",
  "/api/auth/login",
  "/api/public-url",
  "/api/v1/auth/login",
  "/api/v1/ingest",
  "/health",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }
  // GitHub Actions / cloud_collect — Bearer で API v1 を直接呼ぶ
  if (
    pathname.startsWith("/api/v1/") &&
    request.headers.get("authorization")?.startsWith("Bearer ")
  ) {
    return NextResponse.next();
  }

  const token = request.cookies.get("helix_token")?.value;
  if (!token) {
    if (pathname === "/") {
      return NextResponse.redirect(new URL("/welcome", request.url));
    }
    const login = new URL("/login", request.url);
    login.searchParams.set("from", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
