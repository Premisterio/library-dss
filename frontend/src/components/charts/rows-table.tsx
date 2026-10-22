import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cellText } from "@/lib/chart-text"
import { columnsOf } from "@/lib/charts"
import { cn } from "@/lib/utils"

/** The tidy table itself: every column and row, as exports have it. */
export function RowsTable({ chart }: { chart: Chart }) {
  const label = useLabel()
  const columns = columnsOf(chart)
  return (
    <div className="max-h-96 overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((c) => (
              <TableHead key={c.key} className={cn(c.measure && "text-right")}>
                {c.measure ? label("metric", c.key) : label("dimension", c.key)}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {chart.rows.map((row, i) => (
            // oxlint-disable-next-line react/no-array-index-key -- rows never change once loaded, and dimension values alone may repeat
            <TableRow key={i}>
              {columns.map((c) => (
                <TableCell key={c.key} className={cn(c.measure && "text-right tabular-nums")}>
                  {cellText(c, row, label)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
