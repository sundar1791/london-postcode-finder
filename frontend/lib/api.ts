import type { Allocation } from "./dimensions";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- payload shape varies by event; typed in lib/run.ts
export type StreamEvent = { event: string; data: any };

export class SearchRejected extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

function parseBlock(block: string): StreamEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}

export async function streamSearch(
  body: { token_allocation: Allocation; context_text: string; session_id: string },
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new SearchRejected("unreachable", "The search service can't be reached right now.");
  }

  if (res.status === 429) {
    const payload = await res.json().catch(() => ({}));
    throw new SearchRejected(payload.error ?? "rate_limited", payload.message ?? "Too many searches.");
  }
  if (res.status === 422) {
    const payload = await res.json().catch(() => ({}));
    const msg = payload.detail?.[0]?.msg?.replace(/^Value error, /, "") ?? "Those inputs weren't accepted.";
    throw new SearchRejected("invalid", msg);
  }
  if (!res.ok || !res.body) {
    throw new SearchRejected("server", `The search service returned an error (${res.status}).`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const parsed = parseBlock(buffer.slice(0, idx));
      buffer = buffer.slice(idx + 2);
      if (parsed) onEvent(parsed);
    }
  }
}

export type RecordedRun = {
  recorded_at: string;
  request: { token_allocation: Allocation; context_text: string };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  events: { event: string; data: any; t_ms: number }[];
};

export async function fetchRecordedRun(): Promise<RecordedRun> {
  try {
    const res = await fetch(`${API_URL}/api/demo/recorded`);
    if (res.ok) return await res.json();
  } catch {}
  // Backend unreachable or no recording stored — fall back to the copy shipped with the frontend.
  const local = await fetch("/recorded_run.json");
  if (!local.ok) throw new Error("No recorded run is available.");
  return local.json();
}

export async function fetchKnowledge() {
  const res = await fetch(`${API_URL}/api/knowledge`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Knowledge service returned ${res.status}`);
  return res.json();
}
