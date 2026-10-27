import { useLabel } from "@/api/enums"
import type { ChurnRunDetail } from "@/api/types"
import { ChartPanel } from "@/components/charts/chart-panel"
import { HorizontalBars } from "@/components/charts/horizontal-bars"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDecimal } from "@/lib/format"

const SHOWN = 10

function brierText(value: number): string {
  return formatDecimal(value, 4)
}

/** Which features the chosen model leans on most: the Brier score lost when one is shuffled. */
export function ImportancePanel({ run }: { run: ChurnRunDetail }) {
  const label = useLabel()
  return (
    <ChartPanel
      title="Що впливає на прогноз"
      description={`${SHOWN} найважливіших ознак: наскільки зросла б оцінка Браєра, якби ознаку перемішати між читачами.`}
      empty={run.importance.length === 0}
      chart={
        <HorizontalBars
          data={run.importance.slice(0, SHOWN).map((item) => ({
            name: label("churn_feature", item.feature),
            value: item.brier_increase,
          }))}
          series="Зростання оцінки Браєра"
          format={brierText}
          formatAxis={brierText}
          nameWidth={220}
        />
      }
      table={
        <div className="max-h-96 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ознака</TableHead>
                <TableHead className="text-right">Зростання оцінки Браєра</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {run.importance.map((item) => (
                <TableRow key={item.feature}>
                  <TableCell>{label("churn_feature", item.feature)}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {brierText(item.brier_increase)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      }
    />
  )
}
