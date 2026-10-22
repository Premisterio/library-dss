import { Navigate, useParams } from "react-router"

import { useAnalytics } from "@/api/analytics"
import { useLabel } from "@/api/enums"
import { paths } from "@/app/paths"
import { SectionView } from "@/components/analytics/section-view"
import { QueryView } from "@/components/common/query-view"
import { SegmentedNav } from "@/components/glass/segmented-nav"
import { ToolbarSlot } from "@/components/glass/toolbar"
import { ANALYTICS_TABS, isAnalyticsTab } from "@/lib/sections"
import { useCurrentDataset } from "@/pages/dataset-layout"

export function AnalyticsPage() {
  const dataset = useCurrentDataset()
  const { section } = useParams()
  const label = useLabel()
  const analytics = useAnalytics(dataset.id)
  if (!isAnalyticsTab(section)) {
    return <Navigate to={paths.analytics(dataset.id, ANALYTICS_TABS[0])} replace />
  }
  return (
    <>
      <ToolbarSlot side="center">
        <SegmentedNav
          label="Секції аналітики"
          items={ANALYTICS_TABS.map((key) => ({
            to: paths.analytics(dataset.id, key),
            label: label("analytics_section", key),
          }))}
        />
      </ToolbarSlot>
      <QueryView query={analytics} skeletonClassName="h-64">
        {(sections) => <SectionView section={sections[section]} />}
      </QueryView>
    </>
  )
}
