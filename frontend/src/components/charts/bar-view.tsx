import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { useLabel } from "@/api/enums"
import type { Chart, Dimension, Measure } from "@/api/types"
import { seriesColor } from "@/components/charts/palette"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { measureText, rowNames } from "@/lib/chart-text"
import { numberOf } from "@/lib/charts"
import { formatAxis } from "@/lib/format"

const BAR_HEIGHT = 28
const AXIS_HEIGHT = 40

/** One horizontal bar per row (a category dimension). */
export function BarView({
  chart,
  dimension,
  measure,
}: {
  chart: Chart
  dimension: Dimension
  measure: Measure
}) {
  const label = useLabel()
  const names = rowNames(chart, dimension, label)
  const data = chart.rows.map((row, i) => ({
    name: names[i] ?? "",
    value: numberOf(row[measure.key]),
  }))
  const config = {
    value: { label: label("metric", measure.key), color: seriesColor(0) },
  } satisfies ChartConfig
  return (
    <ChartContainer
      config={config}
      className="aspect-auto w-full"
      style={{ height: BAR_HEIGHT * data.length + AXIS_HEIGHT }}
    >
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} />
        <YAxis dataKey="name" type="category" width={170} tickLine={false} axisLine={false} />
        <XAxis type="number" tickFormatter={(v: number) => formatAxis(v, measure.unit)} />
        <ChartTooltip
          content={<ChartTooltipContent formatter={(v) => measureText(measure, Number(v))} />}
        />
        <Bar dataKey="value" fill="var(--color-value)" radius={4} isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  )
}
