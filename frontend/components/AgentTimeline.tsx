"use client";

import { useEffect, useState, type ReactNode } from "react";
import { areaName } from "@/lib/districts";
import { firstSentence, type RunState } from "@/lib/run";
import WeightDiff from "./WeightDiff";

type Status = "pending" | "active" | "done" | "failed";
type Station = { id: string; title: string; detail?: ReactNode; done: boolean; branches?: ReactNode };

const DECISION_LABEL: Record<string, string> = {
  ignore: "Context noted, weights unchanged",
  adjust: "Adjusted your weights",
  spawn: "Sent out a context agent",
  combination: "Adjusted weights and sent out a context agent",
};

function Elapsed({ since, running }: { since?: number; running: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  if (!since) return null;
  return <span className="tabular">{Math.max(0, Math.round((now - since) / 1000))}s</span>;
}

function buildStations(run: RunState, contextGiven: boolean): Station[] {
  const o = run.orchestrator;
  const stations: Station[] = [];

  stations.push({
    id: "memory",
    title: "Reading what it has learned",
    done: !!run.knowledge,
    detail: run.knowledge
      ? run.knowledge.cold_start
        ? "No memory yet, so this search starts from scratch."
        : `Loaded ${run.knowledge.chars.toLocaleString()} characters of heuristics and recent learnings.`
      : undefined,
  });

  stations.push({
    id: "orchestrator",
    title: o ? DECISION_LABEL[o.type] ?? "Orchestrator decided" : "Orchestrator reading your request",
    done: !!o,
    detail: o ? (
      <div className="space-y-3">
        {contextGiven && o.reasoning && <p>{firstSentence(o.reasoning)}</p>}
        {(o.type === "adjust" || o.type === "combination") && (
          <WeightDiff before={o.original_allocation} after={o.adjusted_allocation} />
        )}
      </div>
    ) : undefined,
  });

  if (o?.spawn || run.spawnStarted) {
    const spawn = run.spawnStarted ?? o?.spawn;
    const c = run.spawnComplete;
    const method = spawn?.web_search_fallback
      ? "web search"
      : `OpenStreetMap for ${spawn?.overpass_query} within 500 m`;
    stations.push({
      id: "spawn",
      title: `Context agent: ${spawn?.intent ?? "checking your request"}`,
      done: !!c,
      detail: c
        ? c.failed
          ? "The live lookup failed, so results aren't filtered by it."
          : `Matches in ${c.districts_matched} of ${c.districts_total} districts${c.from_cache ? " (from a recent cached run)" : ""}.`
        : `Checking ${method} across all 40 districts. A live lookup can take a couple of minutes.`,
    });
  }

  stations.push({
    id: "scoring",
    title: "Scoring 40 districts on 5 dimensions",
    done: !!run.scoring,
    detail: run.scoring
      ? `Weighted with your tokens. Leading: ${run.scoring.top_10
          .slice(0, 3)
          .map((d) => d.district)
          .join(", ")}.`
      : run.scorersDone.length
        ? `${run.scorersDone.length} of 5 scorers done.`
        : undefined,
  });

  const s = run.shortlist;
  stations.push({
    id: "shortlist",
    title: "Shortlisting the top five",
    done: !!s,
    detail: s ? (
      <div className="space-y-1">
        <p>{s.top_5.map((d) => d.district).join(", ")}</p>
        {s.removed_by_spawn_filter.length > 0 && (
          <p className="text-ink-faint">
            Dropped {s.removed_by_spawn_filter.map((d) => d.district).join(", ")}: nothing matching your request nearby.
          </p>
        )}
      </div>
    ) : undefined,
  });

  const shortlist = s?.top_5.map((d) => d.district) ?? [];
  const researchDone = shortlist.length > 0 && shortlist.every((d) => run.research[d]?.status === "done");
  stations.push({
    id: "research",
    title: "Researching each district on the web",
    done: researchDone,
    branches:
      shortlist.length > 0 ? (
        <ul className="mt-2 space-y-1.5">
          {shortlist.map((d) => {
            const r = run.research[d];
            const status = r?.status === "done" ? "done" : r ? "running" : "waiting";
            return (
              <li key={d} className="flex items-center gap-2.5 text-sm">
                <span
                  className={`w-2.5 h-2.5 rounded-full border-2 shrink-0 ${
                    status === "done" ? "bg-accent border-accent" : status === "running" ? "border-accent station-active" : "border-rule-strong"
                  }`}
                  aria-hidden="true"
                />
                <span className="font-semibold tabular w-11">{d}</span>
                <span className="text-ink-faint truncate">
                  {status === "done"
                    ? r?.failed
                      ? "research unavailable"
                      : `${r?.insights.length ?? 0} findings`
                    : status === "running"
                      ? `reading about ${areaName(d) || d}`
                      : "queued"}
                </span>
              </li>
            );
          })}
        </ul>
      ) : undefined,
  });

  stations.push({
    id: "synthesis",
    title: "Writing your recommendations",
    done: !!run.recommendations,
    detail: run.recommendations ? `${run.recommendations.length} recommendations ready.` : undefined,
  });

  const l = run.learning;
  stations.push({
    id: "learning",
    title: "Saving what it learned",
    done: !!l,
    detail: l
      ? `${l.count} new ${l.count === 1 ? "learning" : "learnings"}. Search #${l.query_count ?? "?"}${
          l.distillation_due ? " — it will now distil its memory." : "."
        }`
      : undefined,
  });

  return stations;
}

export default function AgentTimeline({ run, contextGiven }: { run: RunState; contextGiven: boolean }) {
  const stations = buildStations(run, contextGiven);
  const running = run.status === "running";
  const activeIndex = stations.findIndex((s) => !s.done);

  const statusOf = (i: number): Status => {
    if (stations[i].done) return "done";
    if (i === activeIndex) return run.status === "error" ? "failed" : running ? "active" : "pending";
    return "pending";
  };

  return (
    <section aria-label="Agent activity" className="rounded-lg border border-rule bg-raised p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-3 mb-5">
        <h2 className="font-serif text-xl">What the agents are doing</h2>
        <span className="text-sm text-ink-faint">
          {running ? "Working for " : run.status === "done" ? "Finished in " : ""}
          {run.status === "done" && run.done ? (
            <span className="tabular">{Math.round(run.done.duration_ms / 1000)}s</span>
          ) : (
            <Elapsed since={run.startedAt} running={running} />
          )}
        </span>
      </div>

      <ol className="relative" aria-live="polite">
        {stations.map((s, i) => {
          const status = statusOf(i);
          const last = i === stations.length - 1;
          return (
            <li key={s.id} className="relative pl-9 pb-5 last:pb-0 reveal">
              {!last && (
                <span
                  className="absolute left-[9px] top-5 bottom-0 w-1 rounded"
                  style={{ background: status === "done" ? "var(--accent)" : "var(--rule)" }}
                  aria-hidden="true"
                />
              )}
              <span
                className={`absolute left-0 top-0.5 w-[22px] h-[22px] rounded-full border-[3px] bg-raised ${
                  status === "done"
                    ? "border-accent"
                    : status === "active"
                      ? "border-accent station-active"
                      : status === "failed"
                        ? "border-warn"
                        : "border-rule-strong"
                }`}
                aria-hidden="true"
              >
                {status === "done" && <span className="absolute inset-[4px] rounded-full bg-accent" />}
              </span>
              <p
                className={`font-medium leading-snug ${status === "pending" ? "text-ink-faint" : "text-ink"}`}
              >
                {s.title}
                <span className="sr-only">
                  {" "}
                  ({status === "done" ? "done" : status === "active" ? "in progress" : status === "failed" ? "failed" : "waiting"})
                </span>
              </p>
              {s.detail && status !== "pending" && <div className="text-sm text-ink-soft mt-1 leading-relaxed">{s.detail}</div>}
              {s.branches}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
