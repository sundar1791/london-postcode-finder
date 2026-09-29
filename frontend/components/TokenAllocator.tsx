import { DIMENSIONS, PRESETS, total, type Allocation, type Dimension } from "@/lib/dimensions";

type Props = {
  value: Allocation;
  onChange: (next: Allocation) => void;
  disabled?: boolean;
};

export default function TokenAllocator({ value, onChange, disabled }: Props) {
  const spent = total(value);
  const remaining = 100 - spent;

  const set = (key: Dimension, raw: number) => {
    // A slider can take whatever is left, never more — the total can't pass 100.
    const next = Math.max(0, Math.min(raw, value[key] + remaining));
    if (next !== value[key]) onChange({ ...value, [key]: next });
  };

  const activePreset = PRESETS.find((p) => DIMENSIONS.every((d) => p.allocation[d.key] === value[d.key]));

  return (
    <fieldset disabled={disabled} className="min-w-0">
      <legend className="sr-only">Token allocation</legend>

      <div className="flex items-baseline justify-between gap-4 mb-1">
        <h2 className="font-serif text-2xl">Spend 100 tokens</h2>
        <p
          className={`tabular text-sm ${remaining === 0 ? "text-ink-faint" : "text-accent font-semibold"}`}
          aria-live="polite"
        >
          {remaining === 0 ? "All 100 spent" : `${remaining} left to spend`}
        </p>
      </div>
      <p className="text-sm text-ink-soft mb-4">Put more tokens on what you care about most.</p>

      <div className="flex flex-wrap gap-2 mb-6" role="group" aria-label="Presets">
        {PRESETS.map((preset) => {
          const active = activePreset?.name === preset.name;
          return (
            <button
              key={preset.name}
              type="button"
              onClick={() => onChange(preset.allocation)}
              aria-pressed={active}
              className={`text-sm px-3 py-1.5 rounded-full border transition-colors disabled:opacity-50 ${
                active
                  ? "bg-ink text-paper border-ink"
                  : "border-rule-strong text-ink-soft hover:border-ink hover:text-ink"
              }`}
            >
              {preset.name}
            </button>
          );
        })}
      </div>

      <ul className="space-y-4">
        {DIMENSIONS.map((dim) => {
          const v = value[dim.key];
          const id = `tokens-${dim.key}`;
          return (
            <li key={dim.key}>
              <div className="flex items-baseline justify-between gap-3">
                <label htmlFor={id} className="font-medium flex items-center gap-2">
                  <span className="inline-block w-3 h-3 rounded-full" style={{ background: dim.color }} aria-hidden="true" />
                  {dim.label}
                </label>
                <span className="tabular text-lg font-semibold w-10 text-right">{v}</span>
              </div>
              <input
                id={id}
                type="range"
                min={0}
                max={100}
                step={5}
                value={v}
                onChange={(e) => set(dim.key, Number(e.target.value))}
                className="token-range"
                style={{ ["--track" as string]: dim.color, ["--fill" as string]: `${v}%` }}
                aria-describedby={`${id}-hint`}
                aria-valuetext={`${v} tokens`}
              />
              <p id={`${id}-hint`} className="text-xs text-ink-faint -mt-0.5">
                {dim.hint}
              </p>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}
