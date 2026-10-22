import { Navigate, useNavigate, useParams } from "react-router"

import { useAnalytics } from "@/api/analytics"
import { paths } from "@/app/paths"
import { SectionTabs } from "@/components/analytics/section-tabs"
import { SectionView } from "@/components/analytics/section-view"
import { QueryView } from "@/components/common/query-view"
import { ANALYTICS_TABS, isAnalyticsTab } from "@/lib/sections"
import { useCurrentDataset } from "@/pages/dataset-layout"

export function AnalyticsPage() {
  const dataset = useCurrentDataset()
  const { section } = useParams()
  const navigate = useNavigate()
  const analytics = useAnalytics(dataset.id)
  if (!isAnalyticsTab(section)) {
    return <Navigate to={paths.analytics(dataset.id, ANALYTICS_TABS[0])} replace />
  }
  return (
    <SectionTabs
      active={section}
      onChange={(next) => void navigate(paths.analytics(dataset.id, next))}
    >
      <QueryView query={analytics} skeletonClassName="h-64">
        {(sections) => <SectionView section={sections[section]} />}
      </QueryView>
    </SectionTabs>
  )
}
