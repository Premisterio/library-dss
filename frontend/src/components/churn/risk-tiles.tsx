import { useLabel } from "@/api/enums"
import type { ChurnRun } from "@/api/types"
import { StatTile } from "@/components/common/stat-tile"
import { EMPTY, formatDateTime, formatValue } from "@/lib/format"

/** The risk group of the active model: its size and how many of them are likely to leave. */
export function RiskTiles({ run }: { run: ChurnRun }) {
  const label = useLabel()
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <StatTile
        label="Читачів у групі ризику"
        value={formatValue(run.summary?.scored, "count")}
        footnote="платний період закінчується в наступні 30 днів"
      />
      <StatTile
        label="Очікуваний відтік"
        value={formatValue(run.summary?.expected_churners, "count")}
        footnote="читачів: сума ймовірностей відтоку"
      />
      <StatTile
        label="Модель"
        value={run.chosen_model ? label("churn_model", run.chosen_model) : EMPTY}
        footnote={`активна, навчена ${formatDateTime(run.created_at)}`}
      />
    </div>
  )
}
