import { Link } from "react-router"

import type { Dataset } from "@/api/types"
import { paths } from "@/app/paths"
import { StatusBadge } from "@/components/datasets/dataset-badges"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/** A dataset that has no analytics: still importing, or its import failed. */
export function DatasetNotReady({ dataset }: { dataset: Dataset }) {
  const failed = dataset.status === "failed"
  return (
    <Alert variant={failed ? "destructive" : "default"}>
      <AlertTitle className="flex items-center gap-2">
        Датасет «{dataset.name}» <StatusBadge status={dataset.status} />
      </AlertTitle>
      <AlertDescription>
        {failed ? (
          <span>
            Імпорт завершився з помилкою, тож аналітики не буде. Подробиці — у{" "}
            <Link to={paths.datasets} className="underline">
              списку датасетів
            </Link>
            .
          </span>
        ) : (
          "Аналітика з'явиться, щойно імпорт завершиться: сторінка оновиться сама."
        )}
      </AlertDescription>
    </Alert>
  )
}
