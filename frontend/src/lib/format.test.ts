import { describe, expect, it } from "vitest"

import { EMPTY, formatDay, formatHour, formatMonth, formatValue } from "@/lib/format"

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

describe("dates and times", () => {
  it("formats days, months and hours, and a missing date as a dash", () => {
    expect(formatDay("2026-09-30")).toBe("30.09.26")
    expect(formatDay(null)).toBe(EMPTY)
    expect(formatMonth("2026-09-01")).toMatch(/2026/)
    expect(formatHour(7)).toBe("07:00")
  })
})
