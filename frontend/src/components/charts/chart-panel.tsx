import { useState, type ReactNode } from "react"

import { ErrorBoundary } from "@/components/common/error-boundary"
import { PanelCard } from "@/components/common/panel-card"
import { Button } from "@/components/ui/button"

/**
 * A chart in a card. With a `table`, the card switches between the chart and its table; a chart
 * that fails to render shows a message instead, and the rest of the page stays.
 */
export function ChartPanel({
  title,
  description,
  chart,
  table,
  empty = false,
  className,
}: {
  title: ReactNode
  description?: ReactNode
  chart: ReactNode
  table?: ReactNode
  empty?: boolean
  className?: string
}) {
  const [showTable, setShowTable] = useState(false)
  const toggle =
    table === undefined || empty ? undefined : (
      <Button variant="ghost" size="sm" onClick={() => setShowTable((shown) => !shown)}>
        {showTable ? "Графік" : "Таблиця"}
      </Button>
    )
  return (
    <PanelCard title={title} description={description} action={toggle} className={className}>
      {empty ? (
        <p className="text-sm text-muted-foreground">Немає даних за цей період.</p>
      ) : (
        <ErrorBoundary
          fallback={<p className="text-sm text-destructive">Не вдалося показати цей графік.</p>}
        >
          {showTable ? table : chart}
        </ErrorBoundary>
      )}
    </PanelCard>
  )
}
