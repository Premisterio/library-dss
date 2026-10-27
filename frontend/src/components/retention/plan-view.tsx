import { useLabel } from "@/api/enums"
import type { Chart, ReportSection } from "@/api/types"
import { KpiGrid } from "@/components/analytics/kpi-grid"
import { Notes } from "@/components/analytics/notes"
import { ChartPanel } from "@/components/charts/chart-panel"
import { LineView } from "@/components/charts/line-view"
import { RowsTable } from "@/components/charts/rows-table"
import { TidyChart } from "@/components/charts/tidy-chart"
import { EffectsChart } from "@/components/retention/effects-chart"

const DESCRIPTIONS: Partial<Record<string, string>> = {
  budget_curve:
    "Найкращий виграш за меншого бюджету. Де крива вирівнюється, додаткові гроші вже не окупаються.",
  action_effects:
    "Різниця частки відтоку між тими, хто отримав дію, і контрольною групою минулої кампанії. План бере ефект для всіх сегментів, якщо не ввімкнено «Ефекти за сегментами».",
  planned_members: "Від найбільшого виграшу. Ризик відтоку — без дії та з дією.",
}

function PlanChart({ chart }: { chart: Chart }) {
  const label = useLabel()
  const [dimension] = chart.dimensions
  const title = label("chart", chart.key)
  const description = DESCRIPTIONS[chart.key]
  if (chart.key === "budget_curve" && dimension) {
    return (
      <ChartPanel
        title={title}
        description={description}
        chart={<LineView chart={chart} dimension={dimension} measures={chart.measures} />}
        table={<RowsTable chart={chart} />}
        empty={chart.rows.length === 0}
      />
    )
  }
  if (chart.key === "action_effects") {
    return (
      <ChartPanel
        title={title}
        description={description}
        chart={<EffectsChart chart={chart} />}
        table={<RowsTable chart={chart} />}
        empty={chart.rows.length === 0}
      />
    )
  }
  if (chart.key === "planned_members") {
    return (
      <ChartPanel
        title={title}
        description={description}
        chart={<RowsTable chart={chart} />}
        empty={chart.rows.length === 0}
        className="2xl:col-span-2"
      />
    )
  }
  return <TidyChart chart={chart} description={description} />
}

/** A plan of retention actions: notes, KPIs and its charts. */
export function PlanView({ section }: { section: ReportSection }) {
  return (
    <div className="flex flex-col gap-4">
      <Notes notes={section.notes} />
      <KpiGrid kpis={section.kpis} />
      <div className="grid gap-4 2xl:grid-cols-2">
        {section.charts.map((chart) => (
          <PlanChart key={chart.key} chart={chart} />
        ))}
      </div>
    </div>
  )
}
