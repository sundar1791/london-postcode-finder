"use client";

import { useEffect, useRef } from "react";
import { areaName } from "@/lib/districts";
import type { RunState } from "@/lib/run";
import WeightDiff from "./WeightDiff";

const TYPE_TEXT: Record<string, string> = {
  ignore: "Your context didn't change the search, so your weights were used as set.",
  adjust: "Your context shifted how much each dimension counts.",
  spawn: "Your context asked for something the five scores don't measure, so a context agent checked it live.",
  combination: "Your context shifted the weights and sent out a context agent.",
};

export default function WhyDrawer({ run, open, onClose }: { run: RunState; open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const o = run.orchestrator;
  const s = run.shortlist;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-0 ml-auto h-dvh max-h-dvh w-full max-w-xl bg-paper text-ink p-0 backdrop:bg-black/40"
      aria-labelledby="why-title"
    >
      <div className="h-full overflow-y-auto px-5 sm:px-8 py-6">
        <div className="flex items-start justify-between gap-4 mb-6">
          <h2 id="why-title" className="font-serif text-3xl">
            Why these results
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-md border border-rule-strong text-sm hover:border-ink"
          >
            Close
          </button>
        </div>

        {o && (
          <section className="mb-8">
            <h3 className="font-semibold mb-1">The orchestrator&apos;s decision</h3>
            <p className="text-ink-soft mb-3">{TYPE_TEXT[o.type]}</p>
            {o.reasoning && (
              <blockquote className="border-l-4 border-accent pl-4 text-ink-soft leading-relaxed mb-4">
                {o.reasoning}
              </blockquote>
            )}
            {(o.type === "adjust" || o.type === "combination") && (
              <>
                <h4 className="text-sm font-semibold mb-2">Weights, before and after</h4>
                <WeightDiff before={o.original_allocation} after={o.adjusted_allocation} />
              </>
            )}
            {o.synthesiser_instruction && (
              <p className="text-sm text-ink-soft mt-4">
                <span className="font-semibold text-ink">Note passed to the writer: </span>
                {o.synthesiser_instruction}
              </p>
            )}
          </section>
        )}

        {(o?.spawn || run.spawnComplete) && (
          <section className="mb-8">
            <h3 className="font-semibold mb-1">Filtering by your request</h3>
            {run.spawnComplete?.failed ? (
              <p className="text-ink-soft">
                The live lookup for &ldquo;{o?.spawn?.intent}&rdquo;{" "}
                {run.spawnComplete.timed_out ? "ran out of time" : "failed"}, so the shortlist wasn&apos;t filtered by it.
              </p>
            ) : (
              <p className="text-ink-soft">
                Only districts with at least one match for &ldquo;{o?.spawn?.intent}&rdquo;
                {o?.spawn?.overpass_query ? ` (OpenStreetMap ${o.spawn.overpass_query}, within 500 m of the district centre)` : ""}{" "}
                could make the shortlist. {run.spawnComplete?.districts_matched} of {run.spawnComplete?.districts_total}{" "}
                districts qualified.
              </p>
            )}
            {s && s.removed_by_spawn_filter.length > 0 && (
              <>
                <h4 className="text-sm font-semibold mt-4 mb-2">Would have ranked higher, but were removed</h4>
                <ul className="text-sm divide-y divide-rule border-y border-rule">
                  {s.removed_by_spawn_filter.map((d) => (
                    <li key={d.district} className="py-2 flex justify-between gap-3">
                      <span>
                        <span className="font-semibold">{d.district}</span>{" "}
                        <span className="text-ink-faint">{areaName(d.district)}</span>
                      </span>
                      <span className="tabular text-ink-faint">no match nearby</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}

        {run.scoring && (
          <section className="mb-8">
            <h3 className="font-semibold mb-2">Top ten on your weights alone</h3>
            <ol className="text-sm divide-y divide-rule border-y border-rule">
              {run.scoring.top_10.map((d, i) => (
                <li key={d.district} className="py-2 grid grid-cols-[1.5rem_3.5rem_1fr_auto] gap-2">
                  <span className="text-ink-faint tabular">{i + 1}</span>
                  <span className="font-semibold">{d.district}</span>
                  <span className="text-ink-faint truncate">{areaName(d.district)}</span>
                  <span className="tabular">{Math.round(d.weighted_score * 100)}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {run.knowledge && (
          <section className="mb-8">
            <h3 className="font-semibold mb-1">Memory used</h3>
            <p className="text-ink-soft">
              {run.knowledge.cold_start
                ? "Nothing yet. This search ran without any learned heuristics."
                : `The orchestrator and writer both read ${run.knowledge.chars.toLocaleString()} characters of distilled heuristics and recent learnings before starting.`}{" "}
              <a href="/learning" className="text-accent underline underline-offset-2">
                See what it has learned
              </a>
            </p>
          </section>
        )}

        {run.learning && run.learning.learnings.length > 0 && (
          <section>
            <h3 className="font-semibold mb-2">What it took away from this search</h3>
            <ul className="space-y-2 text-sm text-ink-soft">
              {run.learning.learnings.map((l, i) => (
                <li key={i} className="leading-relaxed">
                  {l.content}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </dialog>
  );
}
