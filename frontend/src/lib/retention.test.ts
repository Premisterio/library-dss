import { describe, expect, it } from "vitest"

import { effectAxis, planFrom } from "@/lib/retention"

function form(fields: Record<string, string>): FormData {
  const data = new FormData()
  for (const [name, value] of Object.entries(fields)) data.set(name, value)
  return data
}

describe("planFrom", () => {
  it("reads amounts and leaves empty limits unlimited", () => {
    const plan = planFrom(
      form({
        budget: "3000",
        horizon_months: "6",
        email_cost: "1.5",
        max_emails: "100",
        max_discounts: "",
      })
    )
    expect(plan).toEqual({
      budget: 3000,
      horizon_months: 6,
      email_cost: 1.5,
      max_emails: 100,
      max_discounts: null,
      cautious: false,
      by_segment: false,
    })
  })

  it("turns lowered risk in points and the discount in percent into fractions", () => {
    const plan = planFrom(
      form({
        budget: "100",
        assume: "on",
        email_effect: "2",
        discount_effect: "5",
        discount_pct: "30",
        cautious: "on",
      })
    )
    expect(plan.cautious).toBe(true)
    expect(plan.assumed?.email).toBeCloseTo(-0.02)
    expect(plan.assumed?.discount).toBeCloseTo(-0.05)
    expect(plan.assumed?.discount_pct).toBeCloseTo(0.3)
  })

  it("ignores text that is not a number", () => {
    expect(planFrom(form({ budget: "abc", horizon_months: "" }))).toMatchObject({
      budget: 0,
      horizon_months: 12,
    })
  })
})

describe("effectAxis", () => {
  it("spans round ticks around the values and zero", () => {
    const axis = effectAxis([-0.28, 0.127, -0.05])
    expect(axis.ticks.map((t) => Math.round(t * 100))).toEqual([-30, -20, -10, 0, 10, 20])
    expect(axis.at(-0.3)).toBeCloseTo(0)
    expect(axis.at(0)).toBeCloseTo(0.6)
    expect(axis.at(0.2)).toBeCloseTo(1)
  })

  it("keeps zero on the axis when every effect is on one side", () => {
    const axis = effectAxis([-0.04, -0.01])
    expect(axis.ticks.at(-1)).toBe(0)
    expect(axis.at(0)).toBeCloseTo(1)
    expect(effectAxis([]).ticks).toEqual([0])
  })
})
