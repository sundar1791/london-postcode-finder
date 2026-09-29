import { useRef } from "react";
import { DIMENSIONS, PRESETS, total, type Allocation, type Dimension } from "@/lib/dimensions";

const STEP = 5;

// Set one dimension and keep the total at or under 100: spend what's left first,
// then take tokens from the other dimensions, largest first, so raising a slider
// never gets stuck at a full allocation.
export function rebalance(current: Allocation, key: Dimension, raw: number): Allocation {
  const target = Math.max(0, Math.min(100, Math.round(raw / STEP) * STEP));
  const next = { ...current, [key]: target };
  let over = total(next) - 100;
  while (over > 0) {
    const donor = DIMENSIONS.map((d) => d.key)
      .filter((k) => k !== key && next[k] > 0)
      .sort((a, b) => next[b] - next[a])[0];
    if (!donor) break;
    const take = Math.min(STEP, next[donor], over);
    next[donor] -= take;
    over -= take;
  }
  return next;
}

function TokenSlider({
  id,
  value,
  color,
  disabled,
  onSet,
  describedBy,
}: {
  id: string;
  value: number;
  color: string;
  disabled?: boolean;
  onSet: (v: number) => void;
  describedBy: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<{ x: number; y: number; dragging: boolean } | null>(null);

  const valueAt = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect();
    return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * 100;
  };

  // Native range inputs on iOS only move when the thumb itself is dragged, and a
  // tap on the track does nothing. Handle pointer input ourselves: mouse sets
  // immediately; touch sets on a tap or once the finger moves horizontally, so a
  // vertical swipe over the slider still scrolls the page.
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const mouse = e.pointerType === "mouse";
    gesture.current = { x: e.clientX, y: e.clientY, dragging: mouse };
    if (mouse) onSet(valueAt(e.clientX));
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const g = gesture.current;
    if (!g) return;
    if (!g.dragging) {
      const dx = Math.abs(e.clientX - g.x);
      const dy = Math.abs(e.clientY - g.y);
      if (dx > 6 && dx > dy) g.dragging = true;
      else if (dy > 8) {
        gesture.current = null;
        return;
      }
    }
    if (g.dragging) onSet(valueAt(e.clientX));
  };
  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    const g = gesture.current;
    if (g && !g.dragging) onSet(valueAt(e.clientX));
    gesture.current = null;
  };

  return (
    <div
      ref={trackRef}
      className={`relative flex-1 touch-pan-y select-none ${disabled ? "opacity-50" : "cursor-pointer"}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => (gesture.current = null)}
    >
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={STEP}
        value={value}
        disabled={disabled}
        onChange={(e) => onSet(Number(e.target.value))}
        className="token-range pointer-events-none"
        style={{ ["--track" as string]: color, ["--fill" as string]: `${value}%` }}
        aria-describedby={describedBy}
        aria-valuetext={`${value} tokens`}
      />
    </div>
  );
}

function StepButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className="w-10 h-10 shrink-0 rounded-full border border-rule-strong text-lg leading-none text-ink-soft hover:border-ink hover:text-ink active:bg-accent-soft disabled:opacity-35 disabled:hover:border-rule-strong"
    >
      {children}
    </button>
  );
}

type Props = {
  value: Allocation;
  onChange: (next: Allocation) => void;
  disabled?: boolean;
};

export default function TokenAllocator({ value, onChange, disabled }: Props) {
  const remaining = 100 - total(value);

  const set = (key: Dimension, raw: number) => {
    const next = rebalance(value, key, raw);
    if (DIMENSIONS.some((d) => next[d.key] !== value[d.key])) onChange(next);
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
      <p className="text-sm text-ink-soft mb-4">
        Put more tokens on what you care about most. Raising one takes tokens from the others.
      </p>

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
              <div className="flex items-center gap-2 sm:gap-3">
                <StepButton label={`Fewer tokens for ${dim.label}`} onClick={() => set(dim.key, v - STEP)} disabled={disabled || v === 0}>
                  −
                </StepButton>
                <TokenSlider
                  id={id}
                  value={v}
                  color={dim.color}
                  disabled={disabled}
                  onSet={(n) => set(dim.key, n)}
                  describedBy={`${id}-hint`}
                />
                <StepButton label={`More tokens for ${dim.label}`} onClick={() => set(dim.key, v + STEP)} disabled={disabled || v === 100}>
                  +
                </StepButton>
              </div>
              <p id={`${id}-hint`} className="text-xs text-ink-faint">
                {dim.hint}
              </p>
            </li>
          );
        })}
      </ul>
    </fieldset>
  );
}
