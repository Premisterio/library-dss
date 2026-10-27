import { Trash2Icon } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { useDeleteDataset } from "@/api/datasets"
import { useLabel } from "@/api/enums"
import type { Dataset } from "@/api/types"
import { paths } from "@/app/paths"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { IconButton } from "@/components/common/icon-button"
import { CapabilityBadges, StatusBadge } from "@/components/datasets/dataset-badges"
import { ProblemList } from "@/components/common/problem-list"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { EMPTY, formatDateTime, formatDay, formatValue } from "@/lib/format"

const COLUMNS = 8

function DeleteDataset({ dataset }: { dataset: Dataset }) {
  const remove = useDeleteDataset()
  return (
    <ConfirmDialog
      trigger={<IconButton icon={Trash2Icon} label={`Видалити «${dataset.name}»`} />}
      title="Видалити датасет?"
      description={`«${dataset.name}» буде видалено разом з усіма даними, аналітикою та звітами. Це не можна скасувати.`}
      confirmLabel="Видалити"
      onConfirm={async () => {
        await remove.mutateAsync(dataset)
        toast.success(`Датасет «${dataset.name}» видалено`)
      }}
    />
  )
}

/** The status badge; for a failed import it also opens the list of problems. */
function StatusCell({
  dataset,
  showError,
  onToggle,
}: {
  dataset: Dataset
  showError: boolean
  onToggle: () => void
}) {
  if (!dataset.error) return <StatusBadge status={dataset.status} />
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={showError}
      title="Показати помилки імпорту"
    >
      <StatusBadge status={dataset.status} />
    </button>
  )
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  const label = useLabel()
  const [showError, setShowError] = useState(false)
  return (
    <>
      <TableRow>
        <TableCell className="font-medium">
          {dataset.status === "ready" ? (
            <Link to={paths.dataset(dataset.id)} className="hover:underline">
              {dataset.name}
            </Link>
          ) : (
            dataset.name
          )}
        </TableCell>
        <TableCell>
          {dataset.format ? (
            <Badge variant="secondary">{label("dataset_format", dataset.format)}</Badge>
          ) : (
            EMPTY
          )}
        </TableCell>
        <TableCell>
          <StatusCell
            dataset={dataset}
            showError={showError}
            onToggle={() => setShowError((shown) => !shown)}
          />
        </TableCell>
        <TableCell className="tabular-nums">{formatDay(dataset.as_of)}</TableCell>
        <TableCell className="text-right tabular-nums">
          {formatValue(dataset.row_counts.users, "count")}
        </TableCell>
        <TableCell>
          <CapabilityBadges capabilities={dataset.capabilities} />
        </TableCell>
        <TableCell className="text-muted-foreground">
          {formatDateTime(dataset.created_at)}
        </TableCell>
        <TableCell className="text-right">
          <DeleteDataset dataset={dataset} />
        </TableCell>
      </TableRow>
      {showError && dataset.error && (
        <TableRow>
          <TableCell colSpan={COLUMNS}>
            <ProblemList error={dataset.error} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export function DatasetTable({ datasets }: { datasets: Dataset[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Назва</TableHead>
          <TableHead>Формат</TableHead>
          <TableHead>Стан</TableHead>
          <TableHead>Дата зрізу</TableHead>
          <TableHead className="text-right">Читачів</TableHead>
          <TableHead>Можливості</TableHead>
          <TableHead>Завантажено</TableHead>
          <TableHead>
            <span className="sr-only">Дії</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {datasets.map((dataset) => (
          <DatasetRow key={dataset.id} dataset={dataset} />
        ))}
      </TableBody>
    </Table>
  )
}
