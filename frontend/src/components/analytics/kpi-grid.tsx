import { useLabel } from "@/api/enums"
import type { Kpi } from "@/api/types"
import { StatTile } from "@/components/common/stat-tile"
import { formatValue, windowText } from "@/lib/format"

export function KpiGrid({ kpis }: { kpis: Kpi[] }) {
  const label = useLabel()
  if (kpis.length === 0) return null
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <StatTile
          key={kpi.key}
          label={label("metric", kpi.key)}
          value={formatValue(kpi.value, kpi.unit)}
          footnote={
            kpi.value === null
              ? "немає даних у датасеті"
              : windowText(kpi.window_days) || "станом на дату зрізу"
          }
        />
      ))}
    </div>
  )
}
