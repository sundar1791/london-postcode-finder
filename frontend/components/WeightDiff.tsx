import { DIMENSIONS, type Allocation } from "@/lib/dimensions";

export default function WeightDiff({ before, after }: { before: Allocation; after: Allocation }) {
  return (
    <table className="w-full text-sm tabular">
      <caption className="sr-only">Token weights before and after the orchestrator adjusted them</caption>
      <thead className="sr-only">
        <tr>
          <th>Dimension</th>
          <th>Before</th>
          <th>After</th>
        </tr>
      </thead>
      <tbody>
        {DIMENSIONS.map((d) => {
          const b = before[d.key] ?? 0;
          const a = after[d.key] ?? 0;
          const delta = a - b;
          return (
            <tr key={d.key}>
              <th scope="row" className="text-left font-normal text-ink-soft py-0.5 pr-3 whitespace-nowrap w-28">
                {d.label}
              </th>
              <td className="py-0.5 w-full">
                <div className="relative h-2 rounded bg-rule overflow-hidden" aria-hidden="true">
                  <div className="absolute inset-y-0 left-0 opacity-35" style={{ width: `${b}%`, background: d.color }} />
                  <div className="absolute inset-y-0 left-0" style={{ width: `${a}%`, background: d.color }} />
                </div>
              </td>
              <td className="py-0.5 pl-3 text-right whitespace-nowrap">
                <span className="text-ink-faint">{b}</span>
                <span className="text-ink-faint mx-1">to</span>
                <span className="font-semibold">{a}</span>
                {delta !== 0 && (
                  <span className={`ml-1.5 text-xs ${delta > 0 ? "text-accent" : "text-ink-faint"}`}>
                    ({delta > 0 ? "+" : ""}
                    {delta})
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
