import { useLabel } from "@/api/enums"
import type { ChurnRunDetail } from "@/api/types"
import { StatTile } from "@/components/common/stat-tile"
import { metricText, summaryOf } from "@/lib/churn"
import { EMPTY, formatValue } from "@/lib/format"

function versusRule(text: string): string {
  return `правило «14+ днів без читання»: ${text}`
}

/** The chosen model against the "inactive 14+ days" rule, averaged over the backtest. */
export function QualityTiles({ run }: { run: ChurnRunDetail }) {
  const label = useLabel()
  const chosen = run.chosen_model ? summaryOf(run, run.chosen_model) : undefined
  const rule = summaryOf(run, "inactivity_rule")
  const summary = run.summary
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label="Обрана модель"
        value={run.chosen_model ? label("churn_model", run.chosen_model) : EMPTY}
        footnote={
          summary
            ? `${formatValue(summary.examples, "count")} продовжень, ${summary.cutoffs} зрізів`
            : EMPTY
        }
      />
      <StatTile
        label={label("churn_metric", "brier")}
        value={metricText("brier", chosen?.brier)}
        footnote={`менше — краще; ${versusRule(metricText("brier", rule?.brier))}`}
      />
      <StatTile
        label={label("churn_metric", "roc_auc")}
        value={metricText("roc_auc", chosen?.roc_auc)}
        footnote={versusRule(metricText("roc_auc", rule?.roc_auc))}
      />
      <StatTile
        label={label("churn_metric", "lift")}
        value={metricText("lift", chosen?.lift)}
        footnote="у стільки разів частіше відтік, ніж загалом"
      />
    </div>
  )
}
