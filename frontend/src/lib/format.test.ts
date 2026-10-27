import { describe, expect, it } from "vitest"

import {
  EMPTY,
  formatDay,
  formatDecimal,
  formatHour,
  formatLocalDay,
  formatMonth,
  formatPoints,
  formatValue,
} from "@/lib/format"

describe("formatValue", () => {
  it("formats by unit and keeps unknown values visible", () => {
    expect(formatValue(0.0617, "ratio")).toMatch(/^6,2\s?%$/)
    expect(formatValue(169551, "UAH")).toMatch(/^169\s551 грн$/)
    expect(formatValue(45.91, "minutes")).toBe("45,9 хв")
    expect(formatValue(1_068_960, "minutes")).toMatch(/^17\s816 год$/)
    expect(formatValue(null, "count")).toBe(EMPTY)
    expect(formatValue(undefined, "count")).toBe(EMPTY)
  })
})

describe("scores and changes", () => {
  it("keeps the decimals of a score and signs a change in points", () => {
    expect(formatDecimal(0.6875, 3)).toBe("0,688")
    expect(formatDecimal(0.5, 3)).toBe("0,500")
    expect(formatDecimal(null, 3)).toBe(EMPTY)
    expect(formatPoints(0.1123)).toBe("+11,2 в. п.")
    expect(formatPoints(-0.02)).toBe("-2 в. п.")
  })
})

describe("dates and times", () => {
  it("shows an instant as the local date of the dataset", () => {
    // a period that ends at midnight in Kyiv is 21:00 UTC the day before
    expect(formatLocalDay("2026-10-04T21:00:00Z", "Europe/Kyiv")).toBe("05.10.26")
    expect(formatLocalDay("2026-10-04T21:00:00Z", "UTC")).toBe("04.10.26")
  })

  it("formats days, months and hours, and a missing date as a dash", () => {
    expect(formatDay("2026-09-30")).toBe("30.09.26")
    expect(formatDay(null)).toBe(EMPTY)
    expect(formatMonth("2026-09-01")).toMatch(/2026/)
    expect(formatHour(7)).toBe("07:00")
  })
})
