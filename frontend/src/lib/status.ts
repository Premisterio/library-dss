/** Where a dataset or an import job stands, from the API's status codes. */
import type { Dataset, DatasetStatus, Job } from "@/api/types"
import type { LabelFn } from "@/lib/labels"

const IMPORTING: ReadonlySet<DatasetStatus> = new Set(["pending", "importing"])
const FINISHED: ReadonlySet<Job["status"]> = new Set(["succeeded", "failed"])

export function isImporting(dataset: Dataset | undefined): boolean {
  return dataset !== undefined && IMPORTING.has(dataset.status)
}

export function isFinished(job: Job | undefined): boolean {
  return job !== undefined && FINISHED.has(job.status)
}

/** "Запис у базу: позичення" for the stage `load:loans`. */
export function stageText(stage: string | null | undefined, label: LabelFn): string {
  if (!stage) return "У черзі"
  const [step, table] = stage.split(":")
  return table
    ? `${label("job_stage", step)}: ${label("dataset_table", table).toLowerCase()}`
    : label("job_stage", step)
}
