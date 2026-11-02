import {
  ArrowRightIcon,
  CircleAlertIcon,
  CircleCheckIcon,
  ClockIcon,
  LoaderCircleIcon,
  MinusIcon,
  type LucideIcon,
} from "lucide-react"
import { Link } from "react-router"

import { useChurnRuns } from "@/api/churn"
import { useLabel } from "@/api/enums"
import { useReports } from "@/api/reports"
import type { Dataset } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { QueryView } from "@/components/common/query-view"
import { StatusPill } from "@/components/common/status-pill"
import { Button } from "@/components/ui/button"
import { decisionSteps, type Step, type StepState } from "@/lib/steps"

const STATE: Record<
  StepState,
  { tone: "good" | "critical" | "neutral"; icon: LucideIcon; text: string; spinning?: boolean }
> = {
  done: { tone: "good", icon: CircleCheckIcon, text: "Готово" },
  next: { tone: "neutral", icon: ArrowRightIcon, text: "Наступний крок" },
  running: { tone: "neutral", icon: LoaderCircleIcon, text: "Триває", spinning: true },
  failed: { tone: "critical", icon: CircleAlertIcon, text: "Не вдалося" },
  waiting: { tone: "neutral", icon: ClockIcon, text: "Очікує" },
  unavailable: { tone: "neutral", icon: MinusIcon, text: "Недоступно" },
}

function StepItem({ step }: { step: Step }) {
  const { tone, icon, text, spinning } = STATE[step.state]
  const { action } = step
  return (
    <li className="flex flex-col items-start gap-2">
      <StatusPill tone={tone} icon={icon} spinning={spinning}>
        {text}
      </StatusPill>
      <div className="flex flex-col gap-0.5">
        <p className="text-sm font-medium">{step.title}</p>
        <p className="text-xs text-muted-foreground">{step.detail}</p>
      </div>
      {action &&
        (step.accent ? (
          <Button asChild size="sm" className="mt-auto">
            <Link to={action.to}>{action.label}</Link>
          </Button>
        ) : (
          <Button asChild variant="link" size="sm" className="mt-auto h-auto px-0">
            <Link to={action.to}>{action.label}</Link>
          </Button>
        ))}
    </li>
  )
}

/**
 * Where the analyst stands: the steps from the data to the decisions, each with its state and
 * what to do. The first step that is next or failed carries the view's one accented action.
 */
export function DecisionSteps({ dataset }: { dataset: Dataset }) {
  const runs = useChurnRuns(dataset.id)
  const reports = useReports(dataset.id)
  const label = useLabel()
  return (
    <PanelCard title="Кроки до рішень">
      <QueryView query={runs}>
        {(items) => (
          <QueryView query={reports}>
            {(list) => (
              <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {decisionSteps(dataset, items, list, label).map((step) => (
                  <StepItem key={step.key} step={step} />
                ))}
              </ol>
            )}
          </QueryView>
        )}
      </QueryView>
    </PanelCard>
  )
}
