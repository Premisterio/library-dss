import { useLabel } from "@/api/enums"
import type { Kpi } from "@/api/types"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { formatValue, windowText } from "@/lib/format"

function KpiCard({ kpi }: { kpi: Kpi }) {
  const label = useLabel()
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{label("metric", kpi.key)}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{formatValue(kpi.value, kpi.unit)}</CardTitle>
      </CardHeader>
      <CardFooter className="text-xs text-muted-foreground">
        {kpi.value === null
          ? "немає даних у датасеті"
          : windowText(kpi.window_days) || "станом на дату зрізу"}
      </CardFooter>
    </Card>
  )
}

export function KpiGrid({ kpis }: { kpis: Kpi[] }) {
  if (kpis.length === 0) return null
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <KpiCard key={kpi.key} kpi={kpi} />
      ))}
    </div>
  )
}
