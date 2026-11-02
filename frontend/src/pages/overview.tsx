import { useAnalytics } from "@/api/analytics"
import { SectionView } from "@/components/analytics/section-view"
import { QueryView } from "@/components/common/query-view"
import { DecisionSteps } from "@/components/overview/decision-steps"
import { useCurrentDataset } from "@/pages/dataset-layout"

export function OverviewPage() {
  const dataset = useCurrentDataset()
  const analytics = useAnalytics(dataset.id)
  return (
    <>
      <DecisionSteps dataset={dataset} />
      <QueryView query={analytics} skeletonClassName="h-64">
        {(sections) => <SectionView section={sections.overview} />}
      </QueryView>
    </>
  )
}
