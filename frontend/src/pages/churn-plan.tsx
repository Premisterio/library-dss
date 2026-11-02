import { useState } from "react"

import { useActiveChurnRun } from "@/api/churn"
import { useRetentionPlan } from "@/api/retention"
import type { ChurnRun, PlanIn } from "@/api/types"
import { ChurnNav } from "@/components/churn/churn-nav"
import { NoActiveRun } from "@/components/churn/no-active-run"
import { NoRetention } from "@/components/churn/no-retention"
import { PanelCard } from "@/components/common/panel-card"
import { QueryView } from "@/components/common/query-view"
import { ApprovePlan } from "@/components/retention/approve-plan"
import { PlanForm } from "@/components/retention/plan-form"
import { PlanView } from "@/components/retention/plan-view"
import { supportsRetention } from "@/lib/status"
import { useCurrentDataset } from "@/pages/dataset-layout"

function Planner({ run }: { run: ChurnRun }) {
  const [plan, setPlan] = useState<PlanIn>()
  const preview = useRetentionPlan(run.id, plan)
  return (
    <>
      <PlanForm busy={preview.isFetching} onSubmit={setPlan} />
      {plan && (
        <QueryView query={preview} skeletonClassName="h-64">
          {(section) => (
            <PanelCard
              title="Найкращий план"
              description="Для порівняння — жадібний план, що бере дії за виграшем на гривню, доки вистачає бюджету."
              action={<ApprovePlan run={run} plan={plan} />}
            >
              <PlanView section={section} />
            </PanelCard>
          )}
        </QueryView>
      )}
    </>
  )
}

export function ChurnPlanPage() {
  const dataset = useCurrentDataset()
  const active = useActiveChurnRun(dataset.id)
  return (
    <>
      <ChurnNav datasetId={dataset.id} />
      {supportsRetention(dataset) ? (
        <QueryView query={active} skeletonClassName="h-40">
          {(run) =>
            run ? <Planner key={run.id} run={run} /> : <NoActiveRun datasetId={dataset.id} />
          }
        </QueryView>
      ) : (
        <NoRetention />
      )}
    </>
  )
}
