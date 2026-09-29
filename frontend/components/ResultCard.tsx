import { DIMENSIONS } from "@/lib/dimensions";
import { areaName } from "@/lib/districts";
import type { Recommendation } from "@/lib/run";

export default function ResultCard({ rec }: { rec: Recommendation }) {
  const area = areaName(rec.district);
  return (
    <article className="reveal grid gap-5 sm:grid-cols-[4.5rem_1fr] py-8 border-t border-rule first:border-t-0 first:pt-2">
      <div className="flex sm:block items-baseline gap-3">
        <p className="font-serif text-5xl leading-none text-ink-faint tabular" aria-label={`Rank ${rec.rank}`}>
          {rec.rank}
        </p>
      </div>

      <div className="min-w-0">
        <header className="mb-3">
          <h3 className="font-serif text-3xl leading-tight">
            {rec.district}
            {area && <span className="text-ink-soft text-xl sm:text-2xl font-normal"> {area}</span>}
          </h3>
          <p className="font-serif italic text-lg text-ink-soft mt-1 leading-snug">{rec.verdict}</p>
        </header>

        <div className="grid gap-6 lg:grid-cols-[1fr_14rem]">
          <div className="space-y-3 leading-relaxed max-w-[68ch]">
            <p>{rec.rationale}</p>
            <p>
              <strong className="font-semibold">Tradeoff.</strong> {rec.tradeoff}
            </p>
            <p className="rounded-md bg-accent-soft px-3 py-2 text-sm">
              <strong className="font-semibold">Tip.</strong> {rec.tip}
            </p>
          </div>

          <dl className="space-y-2 self-start text-sm" aria-label={`${rec.district} dimension scores`}>
            {DIMENSIONS.map((d) => {
              const v = rec.scores?.[d.key];
              const pct = v == null ? 0 : Math.round(v * 100);
              return (
                <div key={d.key} className="grid grid-cols-[6.5rem_1fr_2rem] items-center gap-2">
                  <dt className="text-ink-soft">{d.label}</dt>
                  <dd className="h-1.5 rounded bg-rule overflow-hidden" aria-hidden="true">
                    <div className="h-full rounded" style={{ width: `${pct}%`, background: d.color }} />
                  </dd>
                  <dd className="tabular text-right text-ink-faint">{v == null ? "–" : pct}</dd>
                </div>
              );
            })}
            {rec.weighted_score != null && (
              <div className="pt-2 mt-1 border-t border-rule flex justify-between">
                <dt className="text-ink-soft">Match for your tokens</dt>
                <dd className="tabular font-semibold">{Math.round(rec.weighted_score * 100)}</dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </article>
  );
}
