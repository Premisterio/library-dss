import { CheckIcon } from "lucide-react"
import { toast } from "sonner"

import { useActivateChurnRun } from "@/api/churn"
import type { ChurnRun } from "@/api/types"
import { ActivePill } from "@/components/churn/run-status"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { formatDateTime } from "@/lib/format"

/** Which run the report shows, and making it the one decisions use (the view's main action). */
export function RunHeader({ run }: { run: ChurnRun }) {
  const activate = useActivateChurnRun()
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold">Модель від {formatDateTime(run.created_at)}</h2>
        <p className="text-sm text-muted-foreground">
          {run.active
            ? "Рішення щодо утримання спираються на цю модель."
            : "Перегляньте якість і активуйте модель, щоб рішення спиралися на неї."}
        </p>
      </div>
      {run.active ? (
        <ActivePill />
      ) : (
        run.status === "succeeded" && (
          <Button
            disabled={activate.isPending}
            onClick={() =>
              activate.mutate(run, { onSuccess: () => toast.success("Модель активовано") })
            }
          >
            {activate.isPending ? <Spinner /> : <CheckIcon />}
            Активувати
          </Button>
        )
      )}
    </div>
  )
}
