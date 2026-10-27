import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import { seriesColor } from "@/components/charts/palette"
import { numberOf } from "@/lib/charts"
import { formatValue } from "@/lib/format"
import { effectAxis } from "@/lib/retention"
import { cn } from "@/lib/utils"

const ROW =
  "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[14rem_minmax(0,1fr)_12rem]"
const ACTION_COLORS: Partial<Record<string, string>> = {
  email: seriesColor(0),
  discount: seriesColor(1),
}

function share(at: (value: number) => number, value: number): string {
  return `${(at(value) * 100).toFixed(2)}%`
}

/**
 * The campaign's effects of each action: a dot for the difference of churn rates against the
 * control group, a line for its 95% interval and a tick for a segment's shrunk effect, on one
 * axis through zero.
 */
export function EffectsChart({ chart }: { chart: Chart }) {
  const label = useLabel()
  const rows = chart.rows.map((row) => ({
    action: String(row.action),
    segment: String(row.segment),
    effect: numberOf(row.effect),
    low: numberOf(row.effect_low),
    high: numberOf(row.effect_high),
    shrunk: numberOf(row.effect_shrunk),
    treated: numberOf(row.treated),
    control: numberOf(row.control),
  }))
  const { at, ticks } = effectAxis(
    rows.flatMap((row) => [row.low, row.high, row.effect, row.shrunk]).filter((v) => v !== null)
  )
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-2">
        {rows.map((row) => {
          const color = ACTION_COLORS[row.action] ?? seriesColor(2)
          const overall = row.segment === "all"
          return (
            <li
              key={`${row.action}-${row.segment}`}
              className={ROW}
              title={`З дією: ${row.treated ?? "—"}, контрольна група: ${row.control ?? "—"}`}
            >
              <span className={cn("text-[13px]", overall && "font-semibold")}>
                {label("retention_action", row.action)} · {label("retention_segment", row.segment)}
              </span>
              <span className="text-right text-xs text-muted-foreground tabular-nums sm:order-3">
                {formatValue(row.effect, "ratio")}
                {row.low !== null && row.high !== null && (
                  <>
                    {" "}
                    [{formatValue(row.low, "ratio")}; {formatValue(row.high, "ratio")}]
                  </>
                )}
              </span>
              <div className="relative col-span-2 h-5 sm:order-2 sm:col-span-1" aria-hidden>
                <span
                  className="absolute inset-y-0 w-px bg-muted-foreground/50"
                  style={{ left: share(at, 0) }}
                />
                {row.low !== null && row.high !== null && (
                  <span
                    className="absolute top-1/2 h-0.5 -translate-y-1/2 rounded-full"
                    style={{
                      left: share(at, row.low),
                      width: `${((at(row.high) - at(row.low)) * 100).toFixed(2)}%`,
                      background: color,
                    }}
                  />
                )}
                {!overall && row.shrunk !== null && (
                  <span
                    className="absolute top-1/2 h-3.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground"
                    style={{ left: share(at, row.shrunk) }}
                  />
                )}
                {row.effect !== null && (
                  <span
                    className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card"
                    style={{ left: share(at, row.effect), background: color }}
                  />
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <div className={ROW} aria-hidden>
        <span className="hidden sm:block" />
        <div className="relative col-span-2 h-4 text-xs text-muted-foreground tabular-nums sm:col-span-1">
          {ticks.map((tick) => (
            <span
              key={tick}
              className="absolute -translate-x-1/2 whitespace-nowrap"
              style={{ left: share(at, tick) }}
            >
              {formatValue(tick, "ratio")}
            </span>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-muted-foreground" />
          ефект і 95-відсоткові межі
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3.5 w-0.5 rounded-full bg-foreground" />
          уточнений ефект сегмента
        </span>
        <span>Ліворуч від нуля — дія утримує.</span>
      </div>
    </div>
  )
}
