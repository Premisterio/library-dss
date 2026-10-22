import { useMemo, useState } from "react"
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  chooseView,
  columnsOf,
  pivot,
  type Cell,
  type Chart,
  type Dimension,
  type Measure,
} from "@/lib/charts"
import { useLabel } from "@/lib/enums"
import { formatAxis, formatDay, formatMonth, formatValue, windowText } from "@/lib/format"
import { cn } from "@/lib/utils"

const MONTHLY = new Set(["month", "cohort"])
const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
]

type Label = ReturnType<typeof useLabel>

function dimensionText(dimension: Dimension, value: Cell, label: Label): string {
  if (value === null || value === undefined) return "—"
  if (dimension.kind === "time") {
    return MONTHLY.has(dimension.key) ? formatMonth(String(value)) : formatDay(String(value))
  }
  if (dimension.enum) return label(dimension.enum, value)
  if (dimension.key === "hour") return `${String(value).padStart(2, "0")}:00`
  return String(value)
}

function measureText(measure: Measure, value: Cell): string {
  return formatValue(typeof value === "number" ? value : null, measure.unit)
}

function Bars({
  chart,
  dimension,
  measure,
}: {
  chart: Chart
  dimension: Dimension
  measure: Measure
}) {
  const label = useLabel()
  const data = chart.rows.map((row) => ({
    name: dimensionText(dimension, row[dimension.key] ?? null, label),
    value: typeof row[measure.key] === "number" ? row[measure.key] : 0,
  }))
  const config = {
    value: { label: label("metric", measure.key), color: COLORS[0] },
  } satisfies ChartConfig
  return (
    <ChartContainer
      config={config}
      className="aspect-auto w-full"
      style={{ height: 28 * data.length + 40 }}
    >
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid horizontal={false} />
        <YAxis dataKey="name" type="category" width={170} tickLine={false} axisLine={false} />
        <XAxis type="number" tickFormatter={(v: number) => formatAxis(v, measure.unit)} />
        <ChartTooltip
          content={<ChartTooltipContent formatter={(v) => measureText(measure, Number(v))} />}
        />
        <Bar dataKey="value" fill="var(--color-value)" radius={4} isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  )
}

function Lines({
  chart,
  dimension,
  measures,
}: {
  chart: Chart
  dimension: Dimension
  measures: Measure[]
}) {
  const label = useLabel()
  const data = chart.rows.map((row) => ({
    x: dimensionText(dimension, row[dimension.key] ?? null, label),
    ...Object.fromEntries(measures.map((m) => [m.key, row[m.key] ?? null])),
  }))
  const config = Object.fromEntries(
    measures.map((m, i) => [
      m.key,
      { label: label("metric", m.key), color: COLORS[i % COLORS.length] },
    ])
  ) satisfies ChartConfig
  const unit = measures[0]?.unit ?? "count"
  return (
    <ChartContainer config={config} className="aspect-auto h-72 w-full">
      <LineChart data={data} margin={{ left: 8, right: 16 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="x" tickLine={false} minTickGap={32} />
        <YAxis tickFormatter={(v: number) => formatAxis(v, unit)} width={56} />
        <ChartTooltip
          content={<ChartTooltipContent formatter={(v) => formatValue(Number(v), unit)} />}
        />
        {measures.length > 1 && <ChartLegend content={<ChartLegendContent />} />}
        {measures.map((m) => (
          <Line
            key={m.key}
            dataKey={m.key}
            stroke={`var(--color-${m.key})`}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ChartContainer>
  )
}

function Heatmap({
  chart,
  down,
  across,
  measure,
}: {
  chart: Chart
  down: Dimension
  across: Dimension
  measure: Measure
}) {
  const label = useLabel()
  const table = useMemo(() => pivot(chart, down, across, measure), [chart, down, across, measure])
  return (
    <div className="overflow-x-auto">
      <p className="mb-2 text-xs text-muted-foreground">Значення: {label("metric", measure.key)}</p>
      <table className="w-full border-separate border-spacing-0.5 text-xs tabular-nums">
        <thead>
          <tr>
            <th className="px-2 py-1 text-left font-medium text-muted-foreground">
              {label("dimension", down.key)}
            </th>
            {table.across.map((a) => (
              <th
                key={String(a)}
                className="px-1 py-1 text-center font-medium text-muted-foreground"
              >
                {dimensionText(across, a, label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.down.map((d) => (
            <tr key={String(d)}>
              <th className="px-2 py-1 text-left font-normal whitespace-nowrap">
                {dimensionText(down, d, label)}
              </th>
              {table.across.map((a) => {
                const value = table.value(d, a)
                const share = value === null || table.max === 0 ? 0 : value / table.max
                return (
                  <td
                    key={String(a)}
                    title={measureText(measure, value)}
                    className="rounded-sm px-1 py-1 text-center"
                    style={{
                      background: `color-mix(in oklch, var(--chart-1) ${Math.round(share * 85)}%, transparent)`,
                    }}
                  >
                    {measureText(measure, value)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RowsTable({ chart }: { chart: Chart }) {
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
          {chart.rows.map((row) => (
            <TableRow key={JSON.stringify(chart.dimensions.map((d) => row[d.key]))}>
              {columns.map((c) => (
                <TableCell key={c.key} className={cn(c.measure && "text-right tabular-nums")}>
                  {c.measure
                    ? measureText(c.measure, row[c.key] ?? null)
                    : c.dimension
                      ? dimensionText(c.dimension, row[c.key] ?? null, label)
                      : String(row[c.key] ?? "—")}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

/** Any tidy chart of the API, drawn from its description: bars, line, heatmap or table. */
export function TidyChart({ chart, className }: { chart: Chart; className?: string }) {
  const label = useLabel()
  const view = useMemo(() => chooseView(chart), [chart])
  const [showTable, setShowTable] = useState(view.type === "table")
  const window = windowText(chart.window_days)
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>{label("chart", chart.key)}</CardTitle>
        {window && <CardDescription>{window}</CardDescription>}
        {view.type !== "table" && chart.rows.length > 0 && (
          <CardAction>
            <Button variant="ghost" size="sm" onClick={() => setShowTable((v) => !v)}>
              {showTable ? "Графік" : "Таблиця"}
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
        {chart.rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Немає даних за цей період.</p>
        ) : showTable ? (
          <RowsTable chart={chart} />
        ) : view.type === "bars" ? (
          <Bars chart={chart} dimension={view.dimension} measure={view.measure} />
        ) : view.type === "line" ? (
          <Lines chart={chart} dimension={view.dimension} measures={view.measures} />
        ) : view.type === "heatmap" ? (
          <Heatmap chart={chart} down={view.down} across={view.across} measure={view.measure} />
        ) : (
          <RowsTable chart={chart} />
        )}
      </CardContent>
    </Card>
  )
}
