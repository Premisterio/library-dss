/** Text of tidy chart cells: dimension values, measure values and row names. */
import type { Cell, Chart, Dimension, Measure, Row } from "@/api/types"
import { numberOf, type Column } from "@/lib/charts"
import { EMPTY, formatDay, formatHour, formatMonth, formatValue } from "@/lib/format"
import type { LabelFn } from "@/lib/labels"

const MONTHLY = new Set(["month", "cohort"])

export function dimensionText(dimension: Dimension, value: Cell | undefined, label: LabelFn) {
  if (value === null || value === undefined) return EMPTY
  if (dimension.kind === "time") {
    return MONTHLY.has(dimension.key) ? formatMonth(String(value)) : formatDay(String(value))
  }
  if (dimension.enum) return label(dimension.enum, value)
  if (dimension.key === "hour") return formatHour(String(value))
  if (dimension.key === "budget") return formatValue(numberOf(value), "UAH")
  return String(value)
}

export function measureText(measure: Measure, value: Cell | undefined): string {
  return formatValue(numberOf(value), measure.unit)
}

export function cellText(column: Column, row: Row, label: LabelFn): string {
  const value = row[column.key]
  if (column.measure) return measureText(column.measure, value)
  if (column.dimension) return dimensionText(column.dimension, value, label)
  return value === null || value === undefined ? EMPTY : String(value)
}

/**
 * The name of each row by one dimension. Rows that share it (the same title by other authors)
 * get their first attribute added, so no two rows read the same.
 */
export function rowNames(chart: Chart, dimension: Dimension, label: LabelFn): string[] {
  const names = chart.rows.map((row) => dimensionText(dimension, row[dimension.key], label))
  const [attribute] = chart.attributes
  if (!attribute) return names
  const counts = new Map<string, number>()
  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1)
  return names.map((name, i) => {
    const row = chart.rows[i]
    if ((counts.get(name) ?? 0) < 2 || !row) return name
    return `${name} · ${dimensionText(attribute, row[attribute.key], label)}`
  })
}
