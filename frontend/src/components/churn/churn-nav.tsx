import { paths } from "@/app/paths"
import { SegmentedNav } from "@/components/glass/segmented-nav"
import { ToolbarSlot } from "@/components/glass/toolbar"

/** The two churn views, switched in the toolbar. */
export function ChurnNav({ datasetId }: { datasetId: number }) {
  return (
    <ToolbarSlot side="center">
      <SegmentedNav
        label="Розділи відтоку"
        items={[
          { to: paths.churnModel(datasetId), label: "Модель", end: true },
          { to: paths.churnRisk(datasetId), label: "Група ризику" },
        ]}
      />
    </ToolbarSlot>
  )
}
