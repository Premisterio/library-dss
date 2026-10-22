import { describe, expect, it } from "vitest"

import type { Chart, Dimension } from "@/api/types"
import { cellText, dimensionText, rowNames } from "@/lib/chart-text"
import type { LabelFn } from "@/lib/labels"

const label: LabelFn = (group, code) => `${group}:${String(code)}`

const title: Dimension = { key: "title", kind: "category", enum: null, order: null }
const authors: Dimension = { key: "authors", kind: "category", enum: null, order: null }

describe("dimensionText", () => {
  it("formats time by its granularity, enums by label and hours as times", () => {
    const month: Dimension = { key: "month", kind: "time", enum: null, order: null }
    const genre: Dimension = { key: "genre", kind: "category", enum: "genre", order: null }
    const hour: Dimension = { key: "hour", kind: "number", enum: null, order: null }
    expect(dimensionText(month, "2026-09-01", label)).toMatch(/2026/)
    expect(dimensionText(genre, "poetry", label)).toBe("genre:poetry")
    expect(dimensionText(hour, 7, label)).toBe("07:00")
    expect(dimensionText(title, null, label)).toBe("—")
  })
})

describe("rowNames", () => {
  it("adds the first attribute only where names repeat", () => {
    const chart: Chart = {
      key: "top_titles",
      dimensions: [title],
      attributes: [authors],
      measures: [{ key: "loans", unit: "count", window_days: null }],
      window_days: null,
      rows: [
        { title: "Історія України", authors: "Грушевський", loans: 3 },
        { title: "Історія України", authors: "Яковенко", loans: 2 },
        { title: "Кобзар", authors: "Шевченко", loans: 1 },
      ],
    }
    expect(rowNames(chart, title, label)).toEqual([
      "Історія України · Грушевський",
      "Історія України · Яковенко",
      "Кобзар",
    ])
  })
})

describe("cellText", () => {
  it("formats measures by unit and shows missing values as a dash", () => {
    const row = { title: "Кобзар", share: 0.25, loans: null }
    expect(
      cellText(
        { key: "share", measure: { key: "share", unit: "ratio", window_days: null } },
        row,
        label
      )
    ).toMatch(/^25\s?%$/)
    expect(
      cellText(
        { key: "loans", measure: { key: "loans", unit: "count", window_days: null } },
        row,
        label
      )
    ).toBe("—")
    expect(cellText({ key: "title", dimension: title }, row, label)).toBe("Кобзар")
  })
})
