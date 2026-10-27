import { CartesianGrid, Line, LineChart, ReferenceLine, XAxis, YAxis } from "recharts"

import type { CalibrationBin } from "@/api/types"
import { seriesColor } from "@/components/charts/palette"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { formatAxis, formatValue } from "@/lib/format"

const MIN_TOP = 0.05 // keeps a model of rare churn from filling the plot with noise

function percent(value: number): string {
  return formatAxis(value, "ratio")
}

/**
 * Predicted probability against the share that churned, bin by bin. A calibrated model follows
 * the dashed diagonal.
 */
export function CalibrationChart({ bins }: { bins: CalibrationBin[] }) {
  const top = Math.max(MIN_TOP, ...bins.flatMap((bin) => [bin.predicted, bin.observed]))
  const config = {
    observed: { label: "Частка, що пішла", color: seriesColor(0) },
  } satisfies ChartConfig
  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <LineChart data={bins} margin={{ left: 8, right: 16, top: 8, bottom: 16 }}>
        <CartesianGrid />
        <XAxis
          type="number"
          dataKey="predicted"
          domain={[0, top]}
          tickFormatter={percent}
          label={{ value: "Передбачена ймовірність", position: "insideBottom", offset: -8 }}
        />
        <YAxis type="number" domain={[0, top]} tickFormatter={percent} width={56} />
        <ReferenceLine
          segment={[
            { x: 0, y: 0 },
            { x: top, y: top },
          ]}
          stroke="var(--muted-foreground)"
          strokeDasharray="4 4"
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              labelFormatter={(predicted) =>
                `Передбачено ${formatValue(Number(predicted), "ratio")}`
              }
              formatter={(value) => `Пішло ${formatValue(Number(value), "ratio")}`}
            />
          }
        />
        <Line
          dataKey="observed"
          stroke="var(--color-observed)"
          strokeWidth={2}
          dot={{ r: 4, fill: "var(--color-observed)" }}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  )
}
