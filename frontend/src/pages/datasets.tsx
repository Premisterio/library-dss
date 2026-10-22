import { DatabaseIcon } from "lucide-react"

import { useDatasets } from "@/api/datasets"
import { EmptyState } from "@/components/common/empty-state"
import { PanelCard } from "@/components/common/panel-card"
import { QueryView } from "@/components/common/query-view"
import { DatasetTable } from "@/components/datasets/dataset-table"
import { UploadPanel } from "@/components/datasets/upload-panel"

export function DatasetsPage() {
  const datasets = useDatasets()
  return (
    <>
      <UploadPanel />
      <PanelCard
        title="Датасети"
        description="Натисніть на назву готового датасету, щоб відкрити огляд і аналітику."
      >
        <QueryView
          query={datasets}
          isEmpty={(items) => items.length === 0}
          empty={
            <EmptyState
              icon={DatabaseIcon}
              title="Поки що немає датасетів"
              description={
                <>
                  Завантажте файл вище або виконайте <code>dss seed-demo</code>.
                </>
              }
            />
          }
        >
          {(items) => <DatasetTable datasets={items} />}
        </QueryView>
      </PanelCard>
    </>
  )
}
