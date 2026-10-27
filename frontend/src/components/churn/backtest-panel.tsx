import { useLabel } from "@/api/enums"
import type { ChurnRunDetail } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { backtestRows, metricText } from "@/lib/churn"

/** The Brier score of every model at each test cutoff, trained only on the older ones. */
export function BacktestPanel({ run }: { run: ChurnRunDetail }) {
  const label = useLabel()
  const models = run.models.map((summary) => summary.model)
  return (
    <PanelCard
      title="Бектест"
      description="Оцінка Браєра на кожному тестовому зрізі. Зріз 0 — найновіший, кожен наступний на 30 днів раніше; модель щоразу навчено лише на старших даних."
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Зріз</TableHead>
              {models.map((model) => (
                <TableHead key={model} className="text-right">
                  {label("churn_model", model)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {backtestRows(run).map((row) => (
              <TableRow key={row.origin}>
                <TableCell className="tabular-nums">{row.origin}</TableCell>
                {models.map((model) => (
                  <TableCell key={model} className="text-right tabular-nums">
                    {metricText("brier", row.brier[model])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </PanelCard>
  )
}
