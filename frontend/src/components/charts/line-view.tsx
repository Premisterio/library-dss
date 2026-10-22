import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { useLabel } from "@/api/enums"
import type { Chart, Dimension, Measure } from "@/api/types"
import { seriesColor } from "@/components/charts/palette"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { dimensionText, measureText } from "@/lib/chart-text"
import { numberOf } from "@/lib/charts"
import { formatAxis } from "@/lib/format"

/** One line per measure over a time dimension; the measures share one unit. */
export function LineView({
  chart,
  dimension,
  measures,
}: {
  chart: Chart
  dimension: Dimension
  measures: Measure[]
}) {
  const label = useLabel()
  const [first] = measures
  if (!first) return null
  const data = chart.rows.map((row) => ({
    x: dimensionText(dimension, row[dimension.key], label),
    ...Object.fromEntries(measures.map((m) => [m.key, numberOf(row[m.key])])),
  }))
  const config = Object.fromEntries(
    measures.map((m, i) => [m.key, { label: label("metric", m.key), color: seriesColor(i) }])
  ) satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <LineChart data={data} margin={{ left: 8, right: 16 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="x" tickLine={false} minTickGap={32} />
        <YAxis tickFormatter={(v: number) => formatAxis(v, first.unit)} width={56} />
        <ChartTooltip
          content={<ChartTooltipContent formatter={(v) => measureText(first, Number(v))} />}
        />
        {measures.length > 1 && <ChartLegend content={<ChartLegendContent />} />}
        {measures.map((m) => (
          <Line
            key={m.key}
            dataKey={m.key}
            stroke={`var(--color-${m.key})`}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartContainer>
  )
}
