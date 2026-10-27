/** The pairwise judgements of the content decision, as the analyst sets them on Saaty's scale. */
import type { ContentIn, CriterionKey } from "@/api/types"

/** The criteria in the order the API weighs them. */
export const CRITERIA = [
  "demand_searches",
  "author_loans",
  "genre_loans",
  "genre_holds_per_copy",
] as const satisfies readonly CriterionKey[]

/** Every pair once, the left criterion first. */
export const PAIRS: readonly (readonly [CriterionKey, CriterionKey])[] = CRITERIA.flatMap(
  (left, i) => CRITERIA.slice(i + 1).map((right) => [left, right] as const)
)

/** Steps of a pair's scale, from "left 9× more important" to "right 9× more important". */
export const STEPS = [4, 3, 2, 1, 0, -1, -2, -3, -4] as const
export type Step = (typeof STEPS)[number]

export function pairKey([left, right]: readonly [CriterionKey, CriterionKey]): string {
  return `${left}:${right}`
}

/** Saaty's value of a step: 9, 7, 5, 3 for the left criterion, 1 for equal, 1/3 … 1/9 for the right. */
export function valueOf(step: Step): number {
  return step >= 0 ? 2 * step + 1 : 1 / (2 * -step + 1)
}

/** The judgements to send: only the pairs moved off "equal". */
export function judgementsFrom(steps: Readonly<Record<string, Step>>): ContentIn["judgements"] {
  return PAIRS.flatMap((pair) => {
    const step = steps[pairKey(pair)] ?? 0
    return step === 0 ? [] : [{ criterion: pair[0], compared_with: pair[1], value: valueOf(step) }]
  })
}

/** The evaluation's body; undefined while the budget or the cap is not a usable number. */
export function contentBody(
  steps: Readonly<Record<string, Step>>,
  budget: string,
  cap: string
): ContentIn | undefined {
  const money = Number(budget)
  if (budget.trim() === "" || !Number.isFinite(money) || money < 0) return undefined
  const limit = cap.trim() === "" ? null : Number(cap)
  if (limit !== null && (!Number.isInteger(limit) || limit < 1)) return undefined
  return { judgements: judgementsFrom(steps), budget: money, max_per_genre: limit }
}

const ONE_DECIMAL = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 1 })

/** How many times one criterion outweighs the other: "×3", or "×1/3" the other way. */
export function ratioText(value: number): string {
  return value >= 1 ? `×${ONE_DECIMAL.format(value)}` : `×1/${ONE_DECIMAL.format(1 / value)}`
}
