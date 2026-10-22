import { useMemo, useState } from "react"

import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import { BarView } from "@/components/charts/bar-view"
import { HeatmapView } from "@/components/charts/heatmap-view"
import { LineView } from "@/components/charts/line-view"
import { RowsTable } from "@/components/charts/rows-table"
import { ErrorBoundary } from "@/components/common/error-boundary"
import { PanelCard } from "@/components/common/panel-card"
import { Button } from "@/components/ui/button"
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
  const [showTable, setShowTable] = useState(false)
  const empty = chart.rows.length === 0
  const toggle =
    view.type === "table" || empty ? undefined : (
      <Button variant="ghost" size="sm" onClick={() => setShowTable((shown) => !shown)}>
        {showTable ? "Графік" : "Таблиця"}
      </Button>
    )
  return (
    <PanelCard
      title={label("chart", chart.key)}
      description={windowText(chart.window_days) || undefined}
      action={toggle}
      className={className}
    >
      {empty ? (
        <p className="text-sm text-muted-foreground">Немає даних за цей період.</p>
      ) : (
        <ErrorBoundary
          fallback={<p className="text-sm text-destructive">Не вдалося показати цей графік.</p>}
        >
          <ChartBody chart={chart} view={showTable ? { type: "table" } : view} />
        </ErrorBoundary>
      )}
    </PanelCard>
  )
}
