import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const apiPath = `/api/auth/${path.join("/")}`;

  const body = await request.json().catch(() => null);

  const res = await fetch(`${API_URL}${apiPath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));

  const response = NextResponse.json(data, { status: res.status });

  // Set httpOnly session cookie on login/signup success
  if (res.ok && data.token && (apiPath.includes("login") || apiPath.includes("signup"))) {
    response.cookies.set("manualworx_session", data.token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 24 * 60 * 60, // 30 days
    });
  }

  // Clear cookie on logout
  if (apiPath.includes("logout")) {
    response.cookies.delete("manualworx_session");
  }

  return response;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const apiPath = `/api/auth/${path.join("/")}`;

  const cookie = request.cookies.get("manualworx_session");

  const res = await fetch(`${API_URL}${apiPath}`, {
    headers: cookie
      ? { Authorization: `Bearer ${cookie.value}` }
      : {},
  });

  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
