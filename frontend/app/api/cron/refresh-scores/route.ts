// Vercel Cron calls this monthly (see vercel.json) with
// `Authorization: Bearer $CRON_SECRET`; it forwards to the backend, which runs
// the score pre-computation in the background.
export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  const backend = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");

  if (!secret || !backend) {
    return Response.json({ error: "CRON_SECRET and BACKEND_URL must be set" }, { status: 503 });
  }
  if (request.headers.get("authorization") !== `Bearer ${secret}`) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const res = await fetch(`${backend}/api/cron/refresh-scores`, {
    headers: { "X-Cron-Secret": secret },
    cache: "no-store",
  });
  const body = await res.json().catch(() => ({}));
  return Response.json(body, { status: res.status });
}
