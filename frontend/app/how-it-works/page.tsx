import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "How it works · London Postcode Finder",
  description: "The two-pass multi-agent architecture behind London Postcode Finder.",
};

type Kind = "memory" | "agent" | "scorer" | "optional";

const KIND_STYLE: Record<Kind, string> = {
  memory: "border-[var(--line-nightlife)]",
  agent: "border-accent",
  scorer: "border-ink-faint",
  optional: "border-accent border-dashed",
};

function Station({
  title,
  kind,
  children,
  parallel,
}: {
  title: string;
  kind: Kind;
  children: ReactNode;
  parallel?: { label: string; color?: string }[];
}) {
  return (
    <li className="relative pl-12 pb-9 last:pb-0">
      <span
        className={`absolute left-[6px] top-0.5 w-[26px] h-[26px] rounded-full border-4 bg-paper ${KIND_STYLE[kind]}`}
        aria-hidden="true"
      />
      <h3 className="font-semibold text-lg leading-snug">{title}</h3>
      <p className="text-ink-soft leading-relaxed mt-1 max-w-[62ch]">{children}</p>
      {parallel && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="Runs in parallel">
          {parallel.map((p) => (
            <li
              key={p.label}
              className="text-sm rounded-full border border-rule-strong bg-raised pl-2 pr-3 py-1 flex items-center gap-2"
            >
              <span className="w-2.5 h-2.5 rounded-full" style={{ background: p.color ?? "var(--accent)" }} aria-hidden="true" />
              {p.label}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function Legend() {
  const items: [Kind, string][] = [
    ["agent", "Agent: a model making a decision"],
    ["optional", "Agent that only runs when needed"],
    ["scorer", "Scorer: a deterministic lookup"],
    ["memory", "Memory"],
  ];
  return (
    <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-soft mb-8">
      {items.map(([kind, label]) => (
        <li key={kind} className="flex items-center gap-2">
          <span className={`w-4 h-4 rounded-full border-[3px] ${KIND_STYLE[kind]}`} aria-hidden="true" />
          {label}
        </li>
      ))}
    </ul>
  );
}

export default function HowItWorksPage() {
  return (
    <div className="pt-10 sm:pt-14">
      <div className="max-w-2xl mb-12">
        <h1 className="font-serif text-4xl sm:text-5xl leading-[1.08] tracking-tight">How it works</h1>
        <p className="mt-4 text-lg text-ink-soft leading-relaxed">
          A search passes through nine steps in two passes. The first is fast and numerical. The second is slow and
          qualitative, and only looks at the five districts that survived the first.
        </p>
      </div>

      <section aria-labelledby="diagram-title" className="mb-20">
        <h2 id="diagram-title" className="font-serif text-3xl mb-4">
          The line a search travels
        </h2>
        <Legend />

        <div className="relative max-w-3xl">
          {/* main line */}
          <span className="absolute left-[17px] top-2 bottom-2 w-1.5 rounded bg-accent" aria-hidden="true" />
          {/* memory loop: distiller feeds the loader of the next search */}
          <span
            className="absolute -left-1 top-3 bottom-3 w-4 rounded-l-2xl border-l-[3px] border-y-[3px] border-dashed border-[var(--line-nightlife)]"
            aria-hidden="true"
          />
          <ol className="relative">
            <Station title="Knowledge Loader" kind="memory">
              Reads the distilled rules plus the last ten raw notes, and hands them to the orchestrator and the writer.
            </Station>
            <Station title="Orchestrator" kind="agent">
              Reads your tokens and your words, then decides. It ignores context that doesn&apos;t matter, shifts your
              weights when you signal a priority (&ldquo;terrified of crime&rdquo;), or spawns a context agent when you
              ask for something the scores don&apos;t measure (&ldquo;a nursery nearby&rdquo;).
            </Station>
            <Station title="Context Sub-Agent" kind="optional">
              Only when spawned. Turns the request into an OpenStreetMap query (or a web search when there&apos;s no
              map tag for it), counts matches around all 40 districts, and caches the answer for 30 days.
            </Station>
            <Station
              title="Five scorers, in parallel"
              kind="scorer"
              parallel={[
                { label: "Safety", color: "var(--line-safety)" },
                { label: "Green space", color: "var(--line-green)" },
                { label: "Nightlife", color: "var(--line-nightlife)" },
                { label: "Transport", color: "var(--line-transport)" },
                { label: "Affordability", color: "var(--line-rent)" },
              ]}
            >
              Pass one. Each reads a monthly pre-computed score for all 40 districts from police, OpenStreetMap, TfL and
              ONS data. No model is involved, and it finishes in under a second.
            </Station>
            <Station title="Synthesiser, pass one" kind="scorer">
              Multiplies each score by your tokens, ranks the districts, applies the context agent&apos;s filter if one
              ran, and keeps the top five.
            </Station>
            <Station
              title="Five research agents, in parallel"
              kind="agent"
              parallel={[1, 2, 3, 4, 5].map((n) => ({ label: `District ${n}` }))}
            >
              Pass two. One agent per shortlisted district searches the web for recent news, local discussion and
              changes the monthly data can&apos;t see yet.
            </Station>
            <Station title="Synthesiser, pass two" kind="agent">
              Combines scores, research, your context and the memory into five recommendations, each with a verdict, a
              rationale, an honest tradeoff and a practical tip.
            </Station>
            <Station title="Knowledge Writer" kind="memory">
              Saves two or three full-sentence notes about what this search taught it, and counts the search.
            </Station>
            <Station title="Distiller" kind="memory">
              Every ten searches, after your results are already on screen, rewrites the notes into at most twelve rules,
              merging, refining or retiring the old ones. The dashed loop is this memory feeding the next search.
            </Station>
          </ol>
        </div>
      </section>

      <div className="grid gap-12 md:grid-cols-2 max-w-5xl">
        <Explainer title="Scorers are not agents">
          The five data pipelines are deterministic: same input, same number, no judgement. Calling them agents would
          overstate what they do. The judgement lives in three places: the orchestrator deciding what your words mean,
          the context agent deciding how to measure something new, and the research agents deciding what&apos;s worth
          reporting.
        </Explainer>
        <Explainer title="Spawning is a filter, not a sixth score">
          If you need a nursery, a district with none nearby isn&apos;t a slightly worse fit. It&apos;s the wrong fit. So
          the context agent&apos;s result removes districts with zero matches from the shortlist rather than being
          averaged in, where a high nightlife score could drown it out. The &ldquo;Why these results&rdquo; panel shows
          which districts were removed.
        </Explainer>
        <Explainer title="Layered memory instead of retrieval">
          The domain is narrow: 40 districts, five dimensions, a few dozen kinds of request. Rather than retrieving
          similar past searches, it keeps what a long conversation keeps: a compressed summary of the old (the distilled
          rules) and the recent notes word for word. With repeated patterns, the summary gets sharper instead of just
          longer.
        </Explainer>
        <Explainer title="Why two passes">
          Web research is the slow, expensive part, so it only runs on five districts. Cached scores make pass one
          near-instant and immune to flaky public APIs. A whole search costs roughly $0.15 to $0.20 in model calls and
          takes about a minute.
        </Explainer>
      </div>
    </div>
  );
}

function Explainer({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-serif text-2xl mb-2">{title}</h2>
      <p className="text-ink-soft leading-relaxed">{children}</p>
    </section>
  );
}
