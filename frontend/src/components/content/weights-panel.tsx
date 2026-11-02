import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { numberOf } from "@/lib/charts"
import { formatValue } from "@/lib/format"

function percent(value: number): string {
  return `${(value * 100).toFixed(2)}%`
}

/**
 * Each criterion's weight as a dot on 0–100 %, over a band: the weights at which the leading
 * title stays the same while the other weights keep their proportions.
 */
export function WeightsPanel({ weights }: { weights: Chart | undefined }) {
  const label = useLabel()
  return (
    <PanelCard
      title="Ваги та чутливість"
      description="Точка — вага критерію. Смуга — ваги, за яких перша назва рейтингу лишається першою (інші ваги зберігають пропорції)."
    >
      <ul className="flex flex-col gap-4">
        {(weights?.rows ?? []).map((row) => {
          const weight = numberOf(row.weight) ?? 0
          const from = numberOf(row.stable_from) ?? weight
          const to = numberOf(row.stable_to) ?? weight
          return (
            <li key={String(row.criterion)} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3 text-[13px]">
                <span>{label("content_criterion", row.criterion)}</span>
                <span className="text-muted-foreground tabular-nums">
                  <span className="font-semibold text-foreground">
                    {formatValue(weight, "ratio")}
                  </span>{" "}
                  · лідер той самий від {formatValue(from, "ratio")} до {formatValue(to, "ratio")}
                </span>
              </div>
              <div className="relative h-2 rounded-full bg-fill" aria-hidden>
                <span
                  className="absolute inset-y-0 rounded-full bg-chart-1/35"
                  style={{ left: percent(from), width: percent(Math.max(to - from, 0)) }}
                />
                <span
                  className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-chart-1 ring-2 ring-card"
                  style={{ left: percent(weight) }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </PanelCard>
  )
}
