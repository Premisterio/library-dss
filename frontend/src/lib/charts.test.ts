import { describe, expect, it } from "vitest"

import type { Chart, Dimension } from "@/api/types"
import { chooseView, columnsOf, heatStep, orderedValues, pivot } from "@/lib/charts"

function chart(partial: Partial<Chart>): Chart {
  return {
    key: "x",
    dimensions: [],
    measures: [{ key: "loans", unit: "count", window_days: null }],
    attributes: [],
    window_days: null,
    rows: [],
    ...partial,
  }
}

const category: Dimension = { key: "genre", kind: "category", enum: "genre", order: null }
const time: Dimension = { key: "week", kind: "time", enum: null, order: null }
const weekday: Dimension = {
  key: "weekday",
  kind: "category",
  enum: "weekday",
  order: ["mon", "tue", "wed"],
}
const hour: Dimension = { key: "hour", kind: "number", enum: null, order: null }

describe("chooseView", () => {
  it("draws one category dimension as bars", () => {
    const view = chooseView(
      chart({ dimensions: [category], rows: [{ genre: "fantasy", loans: 3 }] })
    )
    expect(view.type).toBe("bars")
  })

  it("draws time as a line of the measures that share the first unit", () => {
    const view = chooseView(
      chart({
        dimensions: [time],
        measures: [
          { key: "searches", unit: "count", window_days: null },
          { key: "share", unit: "ratio", window_days: null },
          { key: "loans", unit: "count", window_days: null },
        ],
        rows: [{ week: "2026-01-05" }, { week: "2026-01-12" }, { week: "2026-01-19" }],
      })
    )
    expect(view).toMatchObject({ type: "line" })
    expect(view.type === "line" && view.measures.map((m) => m.key)).toEqual(["searches", "loans"])
  })

  it("pivots two dimensions with the smaller one across and a ratio measure if any", () => {
    const rows = [0, 1, 2, 3].flatMap((h) =>
      ["mon", "tue", "wed"].map((day) => ({ weekday: day, hour: h, sessions: h, share: 0.1 }))
    )
    const view = chooseView(
      chart({
        dimensions: [weekday, hour],
        measures: [
          { key: "sessions", unit: "count", window_days: null },
          { key: "share", unit: "ratio", window_days: null },
        ],
        rows,
      })
    )
    expect(view).toMatchObject({ type: "heatmap", across: weekday, down: hour })
    expect(view.type === "heatmap" && view.measure.key).toBe("share")
  })

  it("keeps negative values out of heatmaps: the colour ramp starts at zero", () => {
    const action: Dimension = { key: "action", kind: "category", enum: null, order: null }
    const rows = ["email", "discount"].flatMap((a) =>
      ["mon", "tue"].map((day) => ({ action: a, weekday: day, effect: -0.05 }))
    )
    const effects = chart({
      dimensions: [action, weekday],
      measures: [{ key: "effect", unit: "ratio", window_days: null }],
      rows,
    })
    expect(chooseView(effects).type).toBe("table")
  })

  it("falls back to a table for empty or long charts", () => {
    expect(chooseView(chart({ dimensions: [category] })).type).toBe("table")
    const rows = Array.from({ length: 40 }, (_, i) => ({ genre: `g${i}`, loans: i }))
    expect(chooseView(chart({ dimensions: [category], rows })).type).toBe("table")
  })
})

describe("pivot and order", () => {
  it("follows the dimension's order and finds cells", () => {
    const rows = [
      { weekday: "wed", hour: 0, sessions: 5 },
      { weekday: "mon", hour: 0, sessions: 7 },
    ]
    expect(orderedValues(rows, "weekday", ["mon", "tue", "wed"])).toEqual(["mon", "wed"])
    const table = pivot(chart({ rows }), hour, weekday, {
      key: "sessions",
      unit: "count",
      window_days: null,
    })
    expect(table.across).toEqual(["mon", "wed"])
    expect(table.value(0, "mon")).toBe(7)
    expect(table.value(1, "mon")).toBeNull()
    expect(table.max).toBe(7)
  })
})

describe("heatStep", () => {
  it("maps a value to a ramp step; zero is the lightest step, no value no fill", () => {
    expect(heatStep(null, 10)).toBe(0)
    expect(heatStep(0, 10)).toBe(1)
    expect(heatStep(1, 10)).toBe(1)
    expect(heatStep(5, 10)).toBe(4)
    expect(heatStep(10, 10)).toBe(7)
    expect(heatStep(3, 0)).toBe(0)
  })
})

describe("columnsOf", () => {
  it("lists dimensions, then attributes, then measures", () => {
    const authors: Dimension = { key: "authors", kind: "category", enum: null, order: null }
    const columns = columnsOf(chart({ dimensions: [category], attributes: [authors] }))
    expect(columns.map((c) => c.key)).toEqual(["genre", "authors", "loans"])
  })
})
