import { Link } from "react-router"

import type { Job } from "@/api/types"
import { paths } from "@/app/paths"
import { JobProgress } from "@/components/common/job-progress"
import { Button } from "@/components/ui/button"

/** The live state of an import, with a way to the dataset once it is in. */
export function ImportProgress({
  job,
  jobError,
  datasetId,
}: {
  job: Job | undefined
  jobError: unknown
  datasetId: number | undefined
}) {
  return (
    <JobProgress job={job} jobError={jobError} label="Прогрес імпорту">
      {job?.status === "succeeded" && datasetId !== undefined && (
        <Button asChild variant="outline" className="self-start">
          <Link to={paths.dataset(datasetId)}>Відкрити датасет</Link>
        </Button>
      )}
    </JobProgress>
  )
}
