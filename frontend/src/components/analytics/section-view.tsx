import type { Section } from "@/api/types"
import { KpiGrid } from "@/components/analytics/kpi-grid"
import { Notes } from "@/components/analytics/notes"
import { TidyChart } from "@/components/charts/tidy-chart"
import { Alert, AlertTitle } from "@/components/ui/alert"

/** One analytics section: notes, KPIs and every chart. */
export function SectionView({ section }: { section: Section | undefined }) {
  if (!section) {
    return (
      <Alert>
        <AlertTitle>Цієї секції немає в аналітиці датасету.</AlertTitle>
      </Alert>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      <Notes notes={section.notes} />
      <KpiGrid kpis={section.kpis} />
      <div className="grid gap-4 2xl:grid-cols-2">
        {section.charts.map((chart) => (
          <TidyChart key={chart.key} chart={chart} />
        ))}
      </div>
    </div>
  )
}
