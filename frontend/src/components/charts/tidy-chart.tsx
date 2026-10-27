import { useMemo } from "react"

import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import { BarView } from "@/components/charts/bar-view"
import { ChartPanel } from "@/components/charts/chart-panel"
import { HeatmapView } from "@/components/charts/heatmap-view"
import { LineView } from "@/components/charts/line-view"
import { RowsTable } from "@/components/charts/rows-table"
import { chooseView, type ChartView } from "@/lib/charts"
import { windowText } from "@/lib/format"

function ChartBody({ chart, view }: { chart: Chart; view: ChartView }) {
  switch (view.type) {
    case "bars":
      return <BarView chart={chart} dimension={view.dimension} measure={view.measure} />
    case "line":
      return <LineView chart={chart} dimension={view.dimension} measures={view.measures} />
    case "heatmap":
      return (
        <HeatmapView chart={chart} down={view.down} across={view.across} measure={view.measure} />
      )
    default:
      return <RowsTable chart={chart} />
  }
}

/** Any tidy chart of the API, drawn from its description: bars, line, heatmap or table. */
export function TidyChart({ chart, className }: { chart: Chart; className?: string }) {
  const label = useLabel()
  const view = useMemo(() => chooseView(chart), [chart])
  return (
    <ChartPanel
      title={label("chart", chart.key)}
      description={windowText(chart.window_days) || undefined}
      chart={<ChartBody chart={chart} view={view} />}
      table={view.type === "table" ? undefined : <RowsTable chart={chart} />}
      empty={chart.rows.length === 0}
      className={className}
    />
  )
}
