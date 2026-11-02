import { describe, expect, it } from "vitest"

import { parseId, paths } from "@/app/paths"

describe("parseId", () => {
  it("accepts positive integers only", () => {
    expect(parseId("42")).toBe(42)
    const bad = [undefined, "", "abc", "1e1", "-1", "0", "01", "1.5", "99999999999999999"]
    expect(bad.map(parseId)).toEqual(bad.map(() => undefined))
  })
})

describe("paths", () => {
  it("builds the dataset pages", () => {
    expect(paths.dataset(3)).toBe("/d/3")
    expect(paths.analytics(3)).toBe("/d/3/analytics")
    expect(paths.analytics(3, "usage")).toBe("/d/3/analytics/usage")
    expect(paths.reports(3)).toBe("/d/3/reports")
    expect(paths.churnPlan(3)).toBe("/d/3/churn/plan")
  })
})
