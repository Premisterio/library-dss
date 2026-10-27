import { PlayIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { useTrainChurn } from "@/api/churn"
import { paths } from "@/app/paths"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"

/** Queue the training of a model and show its run; `first` makes it the view's main action. */
export function TrainButton({ datasetId, first }: { datasetId: number; first: boolean }) {
  const train = useTrainChurn(datasetId)
  const navigate = useNavigate()
  return (
    <Button
      variant={first ? "default" : "outline"}
      disabled={train.isPending}
      onClick={() =>
        train.mutate(undefined, {
          onSuccess: (accepted) => void navigate(paths.churnModel(datasetId, accepted.run.id)),
        })
      }
    >
      {train.isPending ? <Spinner /> : <PlayIcon />}
      {first ? "Навчити модель" : "Навчити ще раз"}
    </Button>
  )
}
