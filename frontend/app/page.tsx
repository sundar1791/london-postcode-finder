"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import AgentTimeline from "@/components/AgentTimeline";
import ContextInput from "@/components/ContextInput";
import ResultCard from "@/components/ResultCard";
import TokenAllocator from "@/components/TokenAllocator";
import WhyDrawer from "@/components/WhyDrawer";
import { fetchRecordedRun, SearchRejected, streamSearch, type StreamEvent } from "@/lib/api";
import { EMPTY_ALLOCATION, PRESETS, total, type Allocation } from "@/lib/dimensions";
import { applyEvent, initialRun, type RunState } from "@/lib/run";

type Action = { type: "event"; event: StreamEvent } | { type: "reset" };

function reducer(state: RunState, action: Action): RunState {
  if (action.type === "reset") return initialRun();
  return applyEvent(state, action.event);
}

type Blocked = { code: string; message: string };

const BLOCKED_TITLE: Record<string, string> = {
  rate_limited: "You've reached the hourly limit",
  daily_cap: "Today's searches are used up",
  unreachable: "The search service is offline",
  timeout: "That search took too long",
  pipeline_failed: "The search didn't finish",
  model_unavailable: "The AI service is unavailable",
  server: "The search service returned an error",
  invalid: "Those inputs weren't accepted",
};

function sessionId(): string {
  try {
    const existing = sessionStorage.getItem("lpf-session");
    if (existing) return existing;
    const id = crypto.randomUUID();
    sessionStorage.setItem("lpf-session", id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function SearchPage() {
  const [allocation, setAllocation] = useState<Allocation>(PRESETS[3].allocation);
  const [context, setContext] = useState("");
  const [submittedContext, setSubmittedContext] = useState("");
  const [run, dispatch] = useReducer(reducer, undefined, initialRun);
  const [blocked, setBlocked] = useState<Blocked | null>(null);
  const [recorded, setRecorded] = useState<{ recorded_at: string } | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const activityRef = useRef<HTMLDivElement>(null);

  const busy = run.status === "running";
  const problem = blocked ?? (run.status === "error" ? run.error ?? null : null);
  const ready = total(allocation) === 100;
  const hasRun = run.status !== "idle";

  useEffect(() => () => abortRef.current?.abort(), []);

  // On narrow screens the timeline sits below the form; bring it into view when a run starts.
  useEffect(() => {
    if (run.status === "running" && window.matchMedia("(max-width: 1023px)").matches) {
      activityRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [run.status]);

  useEffect(() => {
    if (run.recommendations) resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [run.recommendations]);

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
  };

  const search = async () => {
    if (!ready || busy) return;
    stop();
    const controller = new AbortController();
    abortRef.current = controller;
    setBlocked(null);
    setRecorded(null);
    setSubmittedContext(context.trim());
    dispatch({ type: "reset" });
    try {
      await streamSearch(
        { token_allocation: allocation, context_text: context.trim(), session_id: sessionId() },
        (event) => dispatch({ type: "event", event }),
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      dispatch({ type: "reset" });
      if (err instanceof SearchRejected) setBlocked({ code: err.code, message: err.message });
      else setBlocked({ code: "server", message: "Something went wrong while streaming results." });
    }
  };

  const playRecorded = useCallback(async () => {
    stop();
    const controller = new AbortController();
    abortRef.current = controller;
    setBlocked(null);
    dispatch({ type: "reset" });
    try {
      const rec = await fetchRecordedRun();
      if (controller.signal.aborted) return;
      setRecorded({ recorded_at: rec.recorded_at });
      setAllocation(rec.request.token_allocation);
      setContext(rec.request.context_text);
      setSubmittedContext(rec.request.context_text);
      let last = 0;
      for (const e of rec.events) {
        // Real timings, with long waits (research, synthesis) compressed to a few seconds.
        const gap = Math.min(Math.max(e.t_ms - last, 0), 2500);
        last = e.t_ms;
        await sleep(gap);
        if (controller.signal.aborted) return;
        dispatch({ type: "event", event: { event: e.event, data: e.data } });
      }
    } catch {
      setBlocked({ code: "server", message: "The recorded example couldn't be loaded either." });
    }
  }, []);

  const redo = () => {
    stop();
    dispatch({ type: "reset" });
    setBlocked(null);
    setRecorded(null);
    setContext("");
    setWhyOpen(false);
  };

  const startNew = () => {
    redo();
    setAllocation(EMPTY_ALLOCATION);
  };

  return (
    <div className="pt-10 sm:pt-14">
      <div className="max-w-2xl mb-10 sm:mb-14">
        <h1 className="font-serif text-4xl sm:text-5xl leading-[1.08] tracking-tight">
          Where in London should you live?
        </h1>
        <p className="mt-4 text-lg text-ink-soft leading-relaxed">
          Tell it what matters to you. A small team of AI agents scores 40 postcode districts on safety, green space,
          nightlife, transport and rent, researches the five best fits, and explains the tradeoffs.
        </p>
      </div>

      <div className="grid gap-10 lg:gap-14 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)] items-start">
        <form
          className="space-y-10 lg:sticky lg:top-6"
          onSubmit={(e) => {
            e.preventDefault();
            search();
          }}
        >
          <TokenAllocator value={allocation} onChange={setAllocation} disabled={busy} />
          <ContextInput value={context} onChange={setContext} disabled={busy} />

          <div className="space-y-3">
            <button
              type="submit"
              disabled={!ready || busy}
              className="w-full rounded-md bg-accent text-accent-ink font-semibold py-3 text-base disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110"
            >
              {busy ? "Searching…" : "Find my districts"}
            </button>
            {!ready && (
              <p className="text-sm text-ink-soft text-center">
                {total(allocation) < 100
                  ? `Spend ${100 - total(allocation)} more tokens to search.`
                  : "Your tokens add up to more than 100."}
              </p>
            )}
            {hasRun && !busy && (
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={redo}
                  className="flex-1 rounded-md border border-rule-strong py-2 text-sm hover:border-ink"
                  title="Keep your tokens and try different context"
                >
                  Redo
                </button>
                <button
                  type="button"
                  onClick={startNew}
                  className="flex-1 rounded-md border border-rule-strong py-2 text-sm hover:border-ink"
                  title="Clear everything and start again"
                >
                  Start new
                </button>
              </div>
            )}
          </div>
        </form>

        <div ref={activityRef} className="min-w-0 space-y-8 scroll-mt-4">
          {recorded && (
            <div className="rounded-md border border-accent bg-accent-soft px-4 py-3 text-sm" role="status">
              <strong className="font-semibold">Recorded example run.</strong> This is a replay of a real search from{" "}
              {new Date(recorded.recorded_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}
              , sped up. Nothing is running live.
            </div>
          )}

          {problem && (
            <div className="rounded-lg border border-warn/40 bg-warn-soft p-5" role="alert">
              <h2 className="font-serif text-2xl mb-1">{BLOCKED_TITLE[problem.code] ?? "Something went wrong"}</h2>
              <p className="text-ink-soft mb-4">{problem.message}</p>
              <button
                type="button"
                onClick={playRecorded}
                className="rounded-md bg-ink text-paper px-4 py-2 text-sm font-semibold hover:opacity-90"
              >
                See a recorded example run
              </button>
            </div>
          )}

          {!hasRun && !problem && <IdleExplainer onPlayRecorded={playRecorded} />}

          {hasRun && <AgentTimeline run={run} contextGiven={!!submittedContext} />}

          {run.recommendations && run.recommendations.length > 0 && (
            <section ref={resultsRef} aria-labelledby="results-title" className="scroll-mt-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3 mb-2">
                <h2 id="results-title" className="font-serif text-3xl">
                  Your five districts
                </h2>
                <button
                  type="button"
                  onClick={() => setWhyOpen(true)}
                  className="text-sm text-accent underline underline-offset-4 hover:no-underline"
                >
                  Why these results
                </button>
              </div>
              <div>
                {run.recommendations.map((rec) => (
                  <ResultCard key={rec.district} rec={rec} />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>

      <WhyDrawer run={run} open={whyOpen} onClose={() => setWhyOpen(false)} />
    </div>
  );
}

function IdleExplainer({ onPlayRecorded }: { onPlayRecorded: () => void }) {
  const steps = [
    ["It reads its memory", "Heuristics distilled from every earlier search."],
    ["An orchestrator reads your words", "It may shift your weights, or send out an agent to check something new, like nurseries."],
    ["Five scorers rank 40 districts", "Crime, parks, nightlife, transport and rent, from cached public data."],
    ["Five research agents read the web", "One per shortlisted district, looking for recent local detail."],
    ["A writer explains the tradeoffs", "Then it saves what it learned for next time."],
  ];
  return (
    <section className="rounded-lg border border-dashed border-rule-strong p-6 sm:p-8">
      <h2 className="font-serif text-2xl mb-5">What happens when you search</h2>
      <ol className="relative space-y-5">
        {steps.map(([title, body], i) => (
          <li key={title} className="relative pl-9">
            {i < steps.length - 1 && (
              <span className="absolute left-[9px] top-5 -bottom-5 w-1 rounded bg-rule" aria-hidden="true" />
            )}
            <span className="absolute left-0 top-0.5 w-[22px] h-[22px] rounded-full border-[3px] border-rule-strong bg-paper" aria-hidden="true" />
            <p className="font-medium">{title}</p>
            <p className="text-sm text-ink-soft">{body}</p>
          </li>
        ))}
      </ol>
      <p className="text-sm text-ink-soft mt-6">
        A live search takes about a minute.{" "}
        <button type="button" onClick={onPlayRecorded} className="text-accent underline underline-offset-2">
          Watch a recorded example
        </button>{" "}
        first if you&apos;d like to see one.
      </p>
    </section>
  );
}
