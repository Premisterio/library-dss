import { Trash2Icon } from "lucide-react"
import { toast } from "sonner"

import { useLabel } from "@/api/enums"
import { useDeleteReport } from "@/api/reports"
import type { Report } from "@/api/types"
import { ConfirmDialog } from "@/components/common/confirm-dialog"
import { IconButton } from "@/components/common/icon-button"
import { ReportDownloads } from "@/components/reports/report-downloads"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDateTime } from "@/lib/format"

function DeleteReport({ report }: { report: Report }) {
  const remove = useDeleteReport()
  return (
    <ConfirmDialog
      trigger={<IconButton icon={Trash2Icon} label={`Видалити звіт «${report.title}»`} />}
      title="Видалити звіт?"
      description={`Звіт «${report.title}» буде видалено. Аналітика датасету залишиться. Це не можна скасувати.`}
      confirmLabel="Видалити"
      onConfirm={async () => {
        await remove.mutateAsync(report)
        toast.success(`Звіт «${report.title}» видалено`)
      }}
    />
  )
}

export function ReportTable({ reports }: { reports: Report[] }) {
  const label = useLabel()
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Назва</TableHead>
          <TableHead>Секції</TableHead>
          <TableHead>Створено</TableHead>
          <TableHead className="text-right">Дії</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {reports.map((report) => (
          <TableRow key={report.id}>
            <TableCell className="font-medium">{report.title}</TableCell>
            <TableCell className="max-w-md whitespace-normal text-muted-foreground">
              {report.sections.map((key) => label("analytics_section", key)).join(", ")}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDateTime(report.created_at)}
            </TableCell>
            <TableCell>
              <div className="flex justify-end gap-1">
                <ReportDownloads report={report} />
                <DeleteReport report={report} />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
