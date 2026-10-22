import { Link } from "react-router"

import { errorMessage } from "@/api/problem"
import type { Job } from "@/api/types"
import { useLabel } from "@/api/enums"
import { paths } from "@/app/paths"
import { ProblemList } from "@/components/datasets/problem-list"
import { Alert, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { formatValue } from "@/lib/format"
import { stageText } from "@/lib/status"

/** The live state of an import: stage, progress, the result, or why it is not known right now. */
export function ImportProgress({
  job,
  jobError,
  datasetId,
}: {
  job: Job | undefined
  jobError: unknown
  datasetId: number | undefined
}) {
  const label = useLabel()
  const progress = job?.progress ?? 0
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <div className="flex items-center justify-between text-sm">
        <span>{job ? stageText(job.stage, label) : "Очікуємо виконавця…"}</span>
        <span className="text-muted-foreground tabular-nums">{formatValue(progress, "ratio")}</span>
      </div>
      <Progress value={progress * 100} aria-label="Прогрес імпорту" />
      {jobError !== undefined && (
        <Alert>
          <AlertTitle>
            Не вдалося отримати стан імпорту: {errorMessage(jobError)} Пробуємо знову…
          </AlertTitle>
        </Alert>
      )}
      {job?.status === "failed" && job.error && <ProblemList error={job.error} />}
      {job?.status === "succeeded" && datasetId !== undefined && (
        <Button asChild variant="outline" className="self-start">
          <Link to={paths.dataset(datasetId)}>Відкрити датасет</Link>
        </Button>
      )}
    </div>
  )
}
