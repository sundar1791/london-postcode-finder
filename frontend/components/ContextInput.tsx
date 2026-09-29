const EXAMPLES = [
  "I'm terrified of crime",
  "I need a nursery nearby for my daughter",
  "I love parks and quiet streets",
];

const MAX = 500;

export default function ContextInput({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <label htmlFor="context" className="font-serif text-2xl block">
        Anything else?
      </label>
      <p className="text-sm text-ink-soft mt-1 mb-3">
        Optional. The orchestrator reads this and may shift your weights or send out a new agent to check something
        the scores don&apos;t cover.
      </p>
      <textarea
        id="context"
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX))}
        disabled={disabled}
        rows={3}
        maxLength={MAX}
        placeholder="e.g. I work in Canary Wharf and cycle everywhere"
        className="w-full rounded-md border border-rule-strong bg-raised px-3 py-2.5 text-base leading-relaxed placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-60"
        aria-describedby="context-count"
      />
      <div className="flex flex-wrap items-start justify-between gap-3 mt-2">
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              disabled={disabled}
              onClick={() => onChange(ex)}
              className="text-sm px-2.5 py-1 rounded-md bg-accent-soft text-ink-soft hover:text-ink disabled:opacity-50"
            >
              {ex}
            </button>
          ))}
        </div>
        <span id="context-count" className={`tabular text-xs ${value.length > MAX - 50 ? "text-warn" : "text-ink-faint"}`}>
          {value.length}/{MAX}
        </span>
      </div>
    </div>
  );
}
