import { BrainCircuitIcon } from "lucide-react"
import { useSearchParams } from "react-router"
import { toast } from "sonner"

import { useChurnRun, useChurnRuns, useTrainingJob } from "@/api/churn"
import type { ChurnRun } from "@/api/types"
import { parseId } from "@/app/paths"
import { NoRetention } from "@/components/churn/no-retention"
import { RunHeader } from "@/components/churn/run-header"
import { RunReport } from "@/components/churn/run-report"
import { RunsTable } from "@/components/churn/runs-table"
import { ChurnNav } from "@/components/churn/churn-nav"
import { TrainButton } from "@/components/churn/train-button"
import { EmptyState } from "@/components/common/empty-state"
import { JobProgress } from "@/components/common/job-progress"
import { PanelCard } from "@/components/common/panel-card"
import { ProblemList } from "@/components/common/problem-list"
import { QueryView } from "@/components/common/query-view"
import { isTraining, selectRun } from "@/lib/churn"
import { supportsRetention } from "@/lib/status"
import { useCurrentDataset } from "@/pages/dataset-layout"

function SelectedRun({ run }: { run: ChurnRun }) {
  const job = useTrainingJob(run, (finished) => {
    if (finished.status === "succeeded") toast.success("Модель навчено")
  })
  const detail = useChurnRun(run.id, run.status === "succeeded")
  return (
    <>
      <RunHeader run={run} />
      {isTraining(run) && (
        <PanelCard
          title="Навчання моделі"
          description="Бектест і вибір моделі, пояснення та оцінка ризику для кожного читача."
        >
          <JobProgress
            job={job.data}
            jobError={job.isError ? job.error : undefined}
            label="Прогрес навчання"
          />
        </PanelCard>
      )}
      {run.status === "failed" && run.error && <ProblemList error={run.error} />}
      {run.status === "succeeded" && (
        <QueryView query={detail} skeletonClassName="h-64">
          {(trained) => <RunReport run={trained} />}
        </QueryView>
      )}
    </>
  )
}

export function ChurnModelPage() {
  const dataset = useCurrentDataset()
  const [params] = useSearchParams()
  const runs = useChurnRuns(dataset.id)
  if (!supportsRetention(dataset)) {
    return (
      <>
        <ChurnNav datasetId={dataset.id} />
        <NoRetention />
      </>
    )
  }
  return (
    <>
      <ChurnNav datasetId={dataset.id} />
      <QueryView
        query={runs}
        skeletonClassName="h-40"
        isEmpty={(items) => items.length === 0}
        empty={
          <EmptyState
            icon={BrainCircuitIcon}
            title="Модель відтоку ще не навчено"
            description="Модель вчиться на минулих продовженнях підписок, перевіряється на найновіших і оцінює ризик кожного читача, чий платний період закінчується в наступні 30 днів."
          >
            <TrainButton datasetId={dataset.id} first />
          </EmptyState>
        }
      >
        {(items) => {
          const selected = selectRun(items, parseId(params.get("run") ?? undefined))
          return (
            <>
              <PanelCard
                title="Навчені моделі"
                description="Активна модель — та, на яку спираються рішення щодо утримання."
                action={<TrainButton datasetId={dataset.id} first={false} />}
              >
                <RunsTable runs={items} selected={selected} datasetId={dataset.id} />
              </PanelCard>
              {selected && <SelectedRun key={selected.id} run={selected} />}
            </>
          )
        }}
      </QueryView>
    </>
  )
}
