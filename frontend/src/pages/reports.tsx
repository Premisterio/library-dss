import { FileTextIcon } from "lucide-react"

import { useReports } from "@/api/reports"
import { EmptyState } from "@/components/common/empty-state"
import { PanelCard } from "@/components/common/panel-card"
import { QueryView } from "@/components/common/query-view"
import { CreateReportForm } from "@/components/reports/create-report-form"
import { ReportTable } from "@/components/reports/report-table"
import { useCurrentDataset } from "@/pages/dataset-layout"

export function ReportsPage() {
  const dataset = useCurrentDataset()
  const reports = useReports(dataset.id)
  return (
    <>
      <CreateReportForm dataset={dataset} />
      <PanelCard title="Звіти датасету" description="Найновіші зверху.">
        <QueryView
          query={reports}
          isEmpty={(items) => items.length === 0}
          empty={
            <EmptyState
              icon={FileTextIcon}
              title="Звітів ще немає"
              description="Створіть перший звіт вище."
            />
          }
        >
          {(items) => <ReportTable reports={items} />}
        </QueryView>
      </PanelCard>
    </>
  )
}
