import { Trash2Icon } from "lucide-react"
import { Link } from "react-router"
import { toast } from "sonner"

import { useDeleteChurnRun } from "@/api/churn"
import { useLabel } from "@/api/enums"
import type { ChurnRun } from "@/api/types"
import { paths } from "@/app/paths"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { IconButton } from "@/components/common/icon-button"
import { ActivePill, RunStatus } from "@/components/churn/run-status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { isTraining } from "@/lib/churn"
import { EMPTY, formatDateTime, formatValue } from "@/lib/format"
import { cn } from "@/lib/utils"

function DeleteRun({ run }: { run: ChurnRun }) {
  const remove = useDeleteChurnRun()
  if (isTraining(run)) return null
  return (
    <ConfirmDialog
      trigger={<IconButton icon={Trash2Icon} label="Видалити модель" />}
      title="Видалити модель?"
      description="Модель буде видалено разом з оцінками ризику. Це не можна скасувати."
      confirmLabel="Видалити"
      onConfirm={async () => {
        await remove.mutateAsync(run)
        toast.success("Модель видалено")
      }}
    />
  )
}

/** Every trained (or training) model of the dataset; the shown one is marked. */
export function RunsTable({
  runs,
  selected,
  datasetId,
}: {
  runs: ChurnRun[]
  selected: ChurnRun | undefined
  datasetId: number
}) {
  const label = useLabel()
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Навчено</TableHead>
          <TableHead>Стан</TableHead>
          <TableHead>Обрана модель</TableHead>
          <TableHead className="text-right">Читачів під ризиком</TableHead>
          <TableHead className="w-12" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => {
          const current = run.id === selected?.id
          return (
            <TableRow key={run.id} className={cn(current && "bg-muted/50")}>
              <TableCell>
                <Link
                  to={paths.churnModel(datasetId, run.id)}
                  aria-current={current ? "page" : undefined}
                  className={cn("hover:underline", current && "font-semibold")}
                >
                  {formatDateTime(run.created_at)}
                </Link>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  <RunStatus run={run} />
                  {run.active && <ActivePill />}
                </div>
              </TableCell>
              <TableCell>
                {run.chosen_model ? label("churn_model", run.chosen_model) : EMPTY}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatValue(run.summary?.scored, "count")}
              </TableCell>
              <TableCell className="text-right">
                <DeleteRun run={run} />
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
