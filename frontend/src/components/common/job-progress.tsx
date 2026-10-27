import type { ReactNode } from "react"

import { useLabel } from "@/api/enums"
import { errorMessage } from "@/api/problem"
import type { Job } from "@/api/types"
import { ProblemList } from "@/components/common/problem-list"
import { Alert, AlertTitle } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { formatValue } from "@/lib/format"
import { stageText } from "@/lib/status"

/**
 * The live state of a job: its stage and progress, why it failed, or why its state cannot be
 * read right now. `children` follow, e.g. a link to what the job made.
 */
export function JobProgress({
  job,
  jobError,
  label,
  children,
}: {
  job: Job | undefined
  jobError: unknown
  label: string
  children?: ReactNode
}) {
  const labelOf = useLabel()
  const progress = job?.progress ?? 0
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center justify-between text-sm">
        <span>{job ? stageText(job.stage, labelOf) : "Очікуємо виконавця…"}</span>
        <span className="text-muted-foreground tabular-nums">{formatValue(progress, "ratio")}</span>
      </div>
      <Progress value={progress * 100} aria-label={label} />
      {jobError !== undefined && (
        <Alert>
          <AlertTitle>
            Не вдалося отримати стан задачі: {errorMessage(jobError)} Пробуємо знову…
          </AlertTitle>
        </Alert>
      )}
      {job?.status === "failed" && job.error && <ProblemList error={job.error} />}
      {children}
    </div>
  )
}
