import { useMemo } from "react"

import { useLabel } from "@/api/enums"
import type { Chart, Dimension, Measure } from "@/api/types"
import { dimensionText, measureText } from "@/lib/chart-text"
import { pivot } from "@/lib/charts"

const MAX_TINT = 85 // percent of the chart colour in the largest cell

/** Two dimensions as a pivot table, each cell tinted by its share of the largest value. */
export function HeatmapView({
  chart,
  down,
  across,
  measure,
}: {
  chart: Chart
  down: Dimension
  across: Dimension
  measure: Measure
}) {
  const label = useLabel()
  const table = useMemo(() => pivot(chart, down, across, measure), [chart, down, across, measure])
  return (
    <div className="overflow-x-auto">
      <p className="mb-2 text-xs text-muted-foreground">Значення: {label("metric", measure.key)}</p>
      <table className="w-full border-separate border-spacing-0.5 text-xs tabular-nums">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left font-medium text-muted-foreground">
              {label("dimension", down.key)}
            </th>
            {table.across.map((a) => (
              <th
                key={String(a)}
                className="px-1 py-1 text-center font-medium text-muted-foreground"
              >
                {dimensionText(across, a, label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.down.map((d) => (
            <tr key={String(d)}>
              <th className="px-2 py-1 text-left font-normal whitespace-nowrap">
                {dimensionText(down, d, label)}
              </th>
              {table.across.map((a) => {
                const value = table.value(d, a)
                const share = value === null || table.max === 0 ? 0 : value / table.max
                return (
                  <td
                    key={String(a)}
                    title={measureText(measure, value)}
                    className="rounded-sm px-1 py-1 text-center"
                    style={{
                      background: `color-mix(in oklch, var(--chart-1) ${Math.round(share * MAX_TINT)}%, transparent)`,
                    }}
                  >
                    {measureText(measure, value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
