import { useLabel } from "@/api/enums"
import type { Chart, Dimension, Measure } from "@/api/types"
import { HorizontalBars } from "@/components/charts/horizontal-bars"
import { measureText, rowNames } from "@/lib/chart-text"
import { numberOf } from "@/lib/charts"
import { formatAxis } from "@/lib/format"

/** One horizontal bar per row (a category dimension). */
export function BarView({
  chart,
  dimension,
  measure,
}: {
  chart: Chart
  dimension: Dimension
  measure: Measure
}) {
  const label = useLabel()
  const names = rowNames(chart, dimension, label)
  return (
    <HorizontalBars
      data={chart.rows.map((row, i) => ({
        name: names[i] ?? "",
        value: numberOf(row[measure.key]),
      }))}
      series={label("metric", measure.key)}
      format={(value) => measureText(measure, value)}
      formatAxis={(value) => formatAxis(value, measure.unit)}
    />
  )
}
