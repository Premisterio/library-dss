import { useLabel } from "@/api/enums"
import type { ChurnRunDetail } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { METRICS, metricText } from "@/lib/churn"

/** Every model's metrics, averaged over the backtest; the chosen one is marked. */
export function ModelComparison({ run }: { run: ChurnRunDetail }) {
  const label = useLabel()
  const origins = run.models[0]?.origins ?? 0
  return (
    <PanelCard
      title="Порівняння моделей"
      description={`Середнє за ${origins} тестовими зрізами. Модель обрано за найменшою оцінкою Браєра: рішення спираються на ймовірності, тож важить їхня точність.`}
    >
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Модель</TableHead>
              {METRICS.map((metric) => (
                <TableHead key={metric} className="text-right">
                  {label("churn_metric", metric)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {run.models.map((summary) => (
              <TableRow key={summary.model}>
                <TableCell className="font-medium">
                  <span className="inline-flex flex-wrap items-center gap-2">
                    {label("churn_model", summary.model)}
                    {summary.model === run.chosen_model && (
                      <Badge variant="secondary">обрана</Badge>
                    )}
                  </span>
                </TableCell>
                {METRICS.map((metric) => (
                  <TableCell key={metric} className="text-right tabular-nums">
                    {metricText(metric, summary[metric])}
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
