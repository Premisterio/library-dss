import type { ChurnRunDetail } from "@/api/types"
import { CalibrationChart } from "@/components/charts/calibration-chart"
import { ChartPanel } from "@/components/charts/chart-panel"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { calibrationOf } from "@/lib/churn"
import { formatValue } from "@/lib/format"

/** How well the chosen model's probabilities match what happened on the newest test cutoff. */
export function CalibrationPanel({ run }: { run: ChurnRunDetail }) {
  const bins = calibrationOf(run)
  return (
    <ChartPanel
      title="Калібрування"
      description="Найновіший тестовий зріз, 10 груп однакового розміру за ризиком. Що ближче до діагоналі, то точніші ймовірності."
      empty={bins.length === 0}
      chart={<CalibrationChart bins={bins} />}
      table={
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Група</TableHead>
              <TableHead className="text-right">Передбачено</TableHead>
              <TableHead className="text-right">Пішло</TableHead>
              <TableHead className="text-right">Читачів</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bins.map((bin, i) => (
              // oxlint-disable-next-line react/no-array-index-key -- bins are ordered and never change
              <TableRow key={i}>
                <TableCell>{i + 1}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatValue(bin.predicted, "ratio")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatValue(bin.observed, "ratio")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatValue(bin.members, "count")}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      }
    />
  )
}
