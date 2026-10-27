import { describe, expect, it } from "vitest"

import {
  contentBody,
  judgementsFrom,
  PAIRS,
  pairKey,
  ratioText,
  type Step,
  valueOf,
} from "@/lib/content"

describe("pairwise judgements", () => {
  it("covers every pair of the four criteria once", () => {
    expect(PAIRS).toHaveLength(6)
    expect(new Set(PAIRS.map(pairKey)).size).toBe(6)
  })

  it("maps scale steps to Saaty's values", () => {
    const steps: Step[] = [4, 1, 0, -1, -4]
    expect(steps.map(valueOf)).toEqual([9, 3, 1, 1 / 3, 1 / 9])
  })

  it("sends only the pairs moved off equal", () => {
    const [first, second] = PAIRS
    if (!first || !second) throw new Error("no pairs")
    const judgements = judgementsFrom({ [pairKey(first)]: 2, [pairKey(second)]: 0 })
    expect(judgements).toEqual([{ criterion: first[0], compared_with: first[1], value: 5 }])
  })

  it("builds the body only from usable numbers", () => {
    expect(contentBody({}, "20000", "3")).toEqual({
      judgements: [],
      budget: 20000,
      max_per_genre: 3,
    })
    expect(contentBody({}, "500", "")?.max_per_genre).toBeNull()
    for (const [budget, cap] of [
      ["", "3"],
      ["-1", "3"],
      ["abc", "3"],
      ["100", "0"],
      ["100", "1.5"],
    ]) {
      expect(contentBody({}, budget ?? "", cap ?? "")).toBeUndefined()
    }
  })

  it("writes ratios both ways", () => {
    expect(ratioText(3)).toBe("×3")
    expect(ratioText(1 / 5)).toBe("×1/5")
    expect(ratioText(2.14)).toBe("×2,1")
  })
})
