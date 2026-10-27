import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { seriesColor } from "@/components/charts/palette"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"

const BAR_HEIGHT = 28 // the band per row; the bar itself is thinner, the rest is air
const BAR_SIZE = 16
const AXIS_HEIGHT = 40

export type BarDatum = { name: string; value: number | null }

/** One horizontal bar per named value, in the given order. */
export function HorizontalBars({
  data,
  series,
  format,
  formatAxis,
  nameWidth = 170,
}: {
  data: BarDatum[]
  series: string
  format: (value: number) => string
  formatAxis: (value: number) => string
  nameWidth?: number
}) {
  const config = { value: { label: series, color: seriesColor(0) } } satisfies ChartConfig
  return (
    <ChartContainer
      config={config}
      className="aspect-auto w-full"
      style={{ height: BAR_HEIGHT * data.length + AXIS_HEIGHT }}
    >
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} />
        <YAxis dataKey="name" type="category" width={nameWidth} tickLine={false} axisLine={false} />
        <XAxis type="number" tickFormatter={formatAxis} />
        <ChartTooltip content={<ChartTooltipContent formatter={(v) => format(Number(v))} />} />
        {/* Rounded at the data end, square at the baseline. */}
        <Bar
          dataKey="value"
          fill="var(--color-value)"
          barSize={BAR_SIZE}
          radius={[0, 4, 4, 0]}
          isAnimationActive={false}
        />
      </BarChart>
    </ChartContainer>
  )
}
