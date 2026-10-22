import { DownloadIcon } from "lucide-react"

import { useDownloadReport } from "@/api/reports"
import type { ExportFormat, Report } from "@/api/types"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"

const FORMATS: { value: ExportFormat; label: string }[] = [
  { value: "pdf", label: "PDF" },
  { value: "xlsx", label: "Excel (XLSX)" },
  { value: "csv", label: "CSV (zip)" },
  { value: "json", label: "JSON" },
]

export function ReportDownloads({ report }: { report: Report }) {
  const download = useDownloadReport()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={download.isPending}>
          {download.isPending ? <Spinner /> : <DownloadIcon />}
          Завантажити
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {FORMATS.map((format) => (
          <DropdownMenuItem
            key={format.value}
            onSelect={() => download.mutate({ report, format: format.value })}
          >
            {format.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
