"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { diffLines } from "diff";
import { API_URL, fetchKnowledge } from "@/lib/api";

type Learning = { id: string; category: string; outcome_summary: string | null; created_at: string };
type HistoryEntry = {
  id: string;
  created_at: string;
  query_count: number;
  learnings_consumed: number;
  previous_brain: string | null;
  new_brain: string;
  change_summary: string | null;
};
type Knowledge = {
  distilled_brain: string | null;
  last_distilled: string | null;
  query_count: number;
  distill_every_n: number;
  queries_until_next_distillation: number | null;
  recent_learnings: Learning[];
  distillation_history: HistoryEntry[];
};

const CATEGORY: Record<string, string> = {
  context_methodology: "Handling requests",
  token_pattern: "Token patterns",
  synthesiser_insight: "District insight",
};

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export default function LearningPage() {
  const [data, setData] = useState<Knowledge | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchKnowledge()
      .then(setData)
      .catch(() => setError("The knowledge service can't be reached right now. Try again in a minute."));
  }, []);

  return (
    <div className="pt-10 sm:pt-14">
      <div className="max-w-2xl mb-10">
        <h1 className="font-serif text-4xl sm:text-5xl leading-[1.08] tracking-tight">What the system has learned</h1>
        <p className="mt-4 text-lg text-ink-soft leading-relaxed">
          Every search leaves behind a few notes. Every {data?.distill_every_n ?? 10} searches, a distiller rewrites
          those notes into a short set of rules that the agents read before the next search.
        </p>
      </div>

      {error && (
        <p className="rounded-md border border-warn/40 bg-warn-soft p-4" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p className="text-ink-faint">Loading memory…</p>}

      {data && (
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="min-w-0 space-y-14">
            <section aria-labelledby="brain-title">
              <div className="flex flex-wrap items-baseline justify-between gap-3 mb-4">
                <h2 id="brain-title" className="font-serif text-3xl">
                  Current rules
                </h2>
                <a href={`${API_URL}/api/knowledge/export`} className="text-sm text-accent underline underline-offset-4">
                  Download as knowledge.md
                </a>
              </div>
              {data.distilled_brain ? (
                <div className="prose-brain max-w-[70ch]">
                  <ReactMarkdown>{data.distilled_brain}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-ink-soft rounded-md border border-dashed border-rule-strong p-5">
                  No rules yet. The first distillation runs after search #{data.distill_every_n}. Until then the agents
                  read the raw notes on the right.
                </p>
              )}
            </section>

            <section aria-labelledby="history-title">
              <h2 id="history-title" className="font-serif text-3xl mb-5">
                How the rules changed
              </h2>
              {data.distillation_history.length === 0 ? (
                <p className="text-ink-soft">No distillations yet.</p>
              ) : (
                <ol className="relative">
                  {data.distillation_history.map((h, i) => (
                    <HistoryItem key={h.id} entry={h} last={i === data.distillation_history.length - 1} />
                  ))}
                </ol>
              )}
            </section>
          </div>

          <aside className="space-y-10">
            <section className="rounded-lg border border-rule bg-raised p-5">
              <dl className="grid grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-ink-soft">Searches run</dt>
                  <dd className="font-serif text-4xl tabular">{data.query_count}</dd>
                </div>
                <div>
                  <dt className="text-sm text-ink-soft">Next rewrite in</dt>
                  <dd className="font-serif text-4xl tabular">
                    {data.queries_until_next_distillation ?? "–"}
                    <span className="text-base text-ink-soft font-sans">
                      {" "}
                      {data.queries_until_next_distillation === 1 ? "search" : "searches"}
                    </span>
                  </dd>
                </div>
              </dl>
              <div
                className="mt-4 h-1.5 rounded bg-rule overflow-hidden"
                role="progressbar"
                aria-label="Progress to next distillation"
                aria-valuemin={0}
                aria-valuemax={data.distill_every_n}
                aria-valuenow={data.distill_every_n - (data.queries_until_next_distillation ?? 0)}
              >
                <div
                  className="h-full bg-accent"
                  style={{
                    width: `${((data.distill_every_n - (data.queries_until_next_distillation ?? 0)) / data.distill_every_n) * 100}%`,
                  }}
                />
              </div>
              <p className="text-sm text-ink-faint mt-3">
                {data.last_distilled ? `Last rewritten ${fmtDate(data.last_distilled)}.` : "Never rewritten yet."}
              </p>
            </section>

            <section aria-labelledby="recent-title">
              <h2 id="recent-title" className="font-serif text-2xl mb-3">
                Latest raw notes
              </h2>
              {data.recent_learnings.length === 0 ? (
                <p className="text-ink-soft text-sm">None yet. Run a search to add the first.</p>
              ) : (
                <ul className="divide-y divide-rule border-y border-rule">
                  {data.recent_learnings.map((l) => (
                    <li key={l.id} className="py-3 text-sm">
                      <p className="text-ink-faint text-xs mb-1">
                        {CATEGORY[l.category] ?? l.category}, {fmtDate(l.created_at)}
                      </p>
                      <p className="text-ink-soft leading-relaxed">{l.outcome_summary}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}

function HistoryItem({ entry, last }: { entry: HistoryEntry; last: boolean }) {
  const [open, setOpen] = useState(false);
  const parts = open ? diffLines(entry.previous_brain ?? "", entry.new_brain) : [];
  return (
    <li className="relative pl-9 pb-8 last:pb-0">
      {!last && <span className="absolute left-[9px] top-5 bottom-0 w-1 rounded bg-accent" aria-hidden="true" />}
      <span className="absolute left-0 top-0.5 w-[22px] h-[22px] rounded-full border-[3px] border-accent bg-paper" aria-hidden="true" />
      <p className="font-medium">
        After search #{entry.query_count}
        <span className="text-ink-faint font-normal text-sm">
          {" "}
          {fmtDate(entry.created_at)}, from {entry.learnings_consumed} new notes
        </span>
      </p>
      {entry.change_summary && <p className="text-ink-soft mt-1 leading-relaxed max-w-[70ch]">{entry.change_summary}</p>}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="mt-2 text-sm text-accent underline underline-offset-4"
      >
        {open ? "Hide the changes" : "Show the changes"}
      </button>
      {open && (
        <pre className="mt-3 text-xs leading-relaxed whitespace-pre-wrap rounded-md border border-rule bg-raised p-4 overflow-x-auto">
          {parts.map((p, i) => (
            <span
              key={i}
              className={
                p.added
                  ? "block bg-[color-mix(in_srgb,var(--line-green)_18%,transparent)]"
                  : p.removed
                    ? "block line-through text-ink-faint bg-[color-mix(in_srgb,var(--line-safety)_14%,transparent)]"
                    : "block text-ink-faint"
              }
            >
              {p.value}
            </span>
          ))}
        </pre>
      )}
    </li>
  );
}
