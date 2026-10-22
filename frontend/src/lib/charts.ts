import type { Schemas } from "@/lib/api"

export type Chart = Schemas["ChartOut"]
export type Dimension = Schemas["DimensionOut"]
export type Measure = Schemas["MeasureOut"]
export type Row = Chart["rows"][number]
export type Cell = Row[string]

const MAX_BARS = 25
const MAX_PIVOT_COLUMNS = 24
const MAX_PIVOT_ROWS = 60

/** How a tidy chart is drawn, decided from its description alone. */
export type ChartView =
  | { type: "bars"; dimension: Dimension; measure: Measure }
  | { type: "line"; dimension: Dimension; measures: Measure[] }
  | { type: "heatmap"; down: Dimension; across: Dimension; measure: Measure }
  | { type: "table" }

/** Distinct values of a column in display order: the dimension's `order` first, then as seen. */
export function orderedValues(rows: Row[], key: string, order?: string[] | null): Cell[] {
  const seen = [...new Set(rows.map((row) => row[key] ?? null))]
  if (!order?.length) return seen
  const known = order.filter((value) => seen.includes(value))
  return [...known, ...seen.filter((value) => typeof value !== "string" || !order.includes(value))]
}

export function chooseView(chart: Chart): ChartView {
  const [first, second, ...rest] = chart.dimensions
  const [measure] = chart.measures
  if (!first || !measure || chart.rows.length === 0 || rest.length > 0) return { type: "table" }
  if (!second) {
    if (first.kind === "time" && chart.rows.length > 2) {
      return {
        type: "line",
        dimension: first,
        measures: chart.measures.filter((m) => m.unit === measure.unit),
      }
    }
    return chart.rows.length <= MAX_BARS
      ? { type: "bars", dimension: first, measure }
      : { type: "table" }
  }
  const counts = [first, second].map((d) => orderedValues(chart.rows, d.key, d.order).length)
  const [across, down] = (counts[0] ?? 0) <= (counts[1] ?? 0) ? [first, second] : [second, first]
  const acrossCount = Math.min(...counts)
  const downCount = Math.max(...counts)
  if (acrossCount > MAX_PIVOT_COLUMNS || downCount > MAX_PIVOT_ROWS) return { type: "table" }
  const preferred = chart.measures.find((m) => m.unit === "ratio") ?? measure
  return { type: "heatmap", down, across, measure: preferred }
}

export type Pivot = {
  down: Cell[]
  across: Cell[]
  value: (down: Cell, across: Cell) => number | null
  max: number
}

export function pivot(chart: Chart, down: Dimension, across: Dimension, measure: Measure): Pivot {
  const cells = new Map<string, number | null>()
  let max = 0
  for (const row of chart.rows) {
    const value = row[measure.key]
    const number = typeof value === "number" ? value : null
    cells.set(JSON.stringify([row[down.key], row[across.key]]), number)
    if (number !== null && number > max) max = number
  }
  return {
    down: orderedValues(chart.rows, down.key, down.order),
    across: orderedValues(chart.rows, across.key, across.order),
    value: (d, a) => cells.get(JSON.stringify([d, a])) ?? null,
    max,
  }
}

/** Every column of the tidy table, in the order exports use: dimensions, attributes, measures. */
export function columnsOf(
  chart: Chart
): { key: string; dimension?: Dimension; measure?: Measure }[] {
  return [
    ...chart.dimensions.map((dimension) => ({ key: dimension.key, dimension })),
    ...chart.attributes.map((dimension) => ({ key: dimension.key, dimension })),
    ...chart.measures.map((measure) => ({ key: measure.key, measure })),
  ]
}
