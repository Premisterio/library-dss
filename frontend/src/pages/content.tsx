import { BookPlusIcon } from "lucide-react"
import { useMemo, useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { useApproveContent, useContentEvaluation } from "@/api/content"
import type { ContentIn, Dataset } from "@/api/types"
import { paths } from "@/app/paths"
import { KpiGrid } from "@/components/analytics/kpi-grid"
import { ApproveDialog } from "@/components/common/approve-dialog"
import { EmptyState } from "@/components/common/empty-state"
import { ErrorAlert } from "@/components/common/error-alert"
import { PanelCard } from "@/components/common/panel-card"
import { JudgementsPanel } from "@/components/content/judgements-panel"
import { RankingTable } from "@/components/content/ranking-table"
import { WeightsPanel } from "@/components/content/weights-panel"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useDebounced } from "@/hooks/use-debounced"
import { numberOf } from "@/lib/charts"
import { contentBody, type Step } from "@/lib/content"
import { formatValue } from "@/lib/format"
import { supportsContent } from "@/lib/status"
import { useCurrentDataset } from "@/pages/dataset-layout"

const MAX_CR = 0.1

function ApproveContent({
  datasetId,
  decision,
  disabled,
}: {
  datasetId: number
  decision: ContentIn
  disabled: boolean
}) {
  const approve = useApproveContent(datasetId)
  const navigate = useNavigate()
  return (
    <ApproveDialog
      label="Затвердити портфель"
      title="Затвердити портфель?"
      description="Портфель збережеться як рішення серед звітів датасету разом із судженнями та бюджетом, за якими його складено. Його можна завантажити в PDF, Excel, CSV чи JSON."
      defaultName={`Закупівля, бюджет ${formatValue(decision.budget, "UAH")}`}
      disabled={disabled}
      onApprove={async (title) => {
        const report = await approve.mutateAsync({ title, decision })
        toast.success(`Рішення «${report.title}» збережено`, {
          action: { label: "До звітів", onClick: () => void navigate(paths.reports(datasetId)) },
        })
      }}
    />
  )
}

function Acquisition({ dataset }: { dataset: Dataset }) {
  const [steps, setSteps] = useState<Record<string, Step>>({})
  const [budget, setBudget] = useState("20000")
  const [cap, setCap] = useState("3")
  const body = useMemo(() => contentBody(steps, budget, cap), [steps, budget, cap])
  const settled = useDebounced(body, 300)
  const evaluation = useContentEvaluation(dataset.id, settled)
  const section = evaluation.data
  const chart = (key: string) => section?.charts.find((c) => c.key === key)
  const consistency = section?.kpis.find((kpi) => kpi.key === "consistency_ratio")
  const ranking = chart("title_ranking")
  // Approve only what is on screen: the evaluation of exactly these inputs, consistent enough.
  const current = body !== undefined && body === settled && !evaluation.isPlaceholderData
  const consistent = (numberOf(consistency?.value) ?? 1) <= MAX_CR
  return (
    <>
      <div className="grid gap-4 xl:grid-cols-2">
        <JudgementsPanel
          steps={steps}
          onChange={(key, step) => setSteps((previous) => ({ ...previous, [key]: step }))}
          consistency={consistency}
          inconsistent={chart("inconsistent_judgements")}
        />
        <WeightsPanel weights={chart("criterion_weights")} />
      </div>
      <PanelCard
        title="Портфель"
        description="Назви з найбільшою сумарною оцінкою TOPSIS, ліцензії яких вкладаються в бюджет. Стійкість — частка з 2000 наборів ваг навколо ваших, за яких назва лишається серед стількох перших, скільки їх у портфелі."
        action={
          body && (
            <ApproveContent
              datasetId={dataset.id}
              decision={body}
              disabled={!current || evaluation.isFetching || !consistent}
            />
          )
        }
      >
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:max-w-xl">
            <Field>
              <FieldLabel htmlFor="content-budget">Бюджет на ліцензії, грн</FieldLabel>
              <Input
                id="content-budget"
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={budget}
                onChange={(event) => setBudget(event.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="content-cap">Найбільше назв одного жанру</FieldLabel>
              <Input
                id="content-cap"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                value={cap}
                onChange={(event) => setCap(event.target.value)}
              />
              <FieldDescription>Порожньо — без обмеження.</FieldDescription>
            </Field>
          </div>
          {evaluation.isError && section === undefined && <ErrorAlert error={evaluation.error} />}
          {section === undefined && !evaluation.isError && <Skeleton className="h-64 w-full" />}
          {section && (
            <>
              <KpiGrid kpis={section.kpis} />
              {ranking && <RankingTable ranking={ranking} />}
            </>
          )}
        </div>
      </PanelCard>
    </>
  )
}

export function ContentPage() {
  const dataset = useCurrentDataset()
  if (!supportsContent(dataset)) {
    return (
      <EmptyState
        icon={BookPlusIcon}
        title="Закупівля для цього датасету недоступна"
        description="Потрібні пропозиції дистриб'ютора й пошуки читачів. Їх містять датасети табличного формату (libsim)."
      />
    )
  }
  return <Acquisition dataset={dataset} />
}
