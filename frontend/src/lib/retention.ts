/** The inputs of a retention plan, read from its form. */
import type { PlanIn } from "@/api/types"
import { formText } from "@/lib/forms"

/** What the form shows before the analyst changes anything. */
export const PLAN_DEFAULTS = {
  budget: 5000,
  horizonMonths: 12,
  emailCost: 2,
  emailEffect: 2,
  discountEffect: 5,
  discountPct: 20,
}

function numberOf(form: FormData, name: string): number | undefined {
  const text = formText(form, name)
  if (text === "") return undefined
  const value = Number(text)
  return Number.isFinite(value) ? value : undefined
}

/**
 * The plan's inputs. Money is in UAH; empty limits mean no limit. Assumed effects are typed as
 * how many percentage points an action lowers the churn risk, and the discount in percent.
 */
export function planFrom(form: FormData): PlanIn {
  const plan: PlanIn = {
    budget: numberOf(form, "budget") ?? 0,
    horizon_months: numberOf(form, "horizon_months") ?? PLAN_DEFAULTS.horizonMonths,
    email_cost: numberOf(form, "email_cost") ?? PLAN_DEFAULTS.emailCost,
    max_emails: numberOf(form, "max_emails") ?? null,
    max_discounts: numberOf(form, "max_discounts") ?? null,
    cautious: form.has("cautious"),
    by_segment: form.has("by_segment"),
  }
  if (!form.has("assume")) return plan
  return {
    ...plan,
    assumed: {
      email: -(numberOf(form, "email_effect") ?? 0) / 100,
      discount: -(numberOf(form, "discount_effect") ?? 0) / 100,
      discount_pct: (numberOf(form, "discount_pct") ?? PLAN_DEFAULTS.discountPct) / 100,
    },
  }
}

const AXIS_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1]
const MAX_TICKS = 7

/**
 * An axis for changes of a rate that always shows zero: ticks at a round step, and where a
 * value sits as a share (0..1) of the width.
 */
export function effectAxis(values: number[]): { at: (value: number) => number; ticks: number[] } {
  const low = Math.min(0, ...values)
  const high = Math.max(0, ...values)
  const span = high - low || AXIS_STEPS[0] || 0.01
  const step = AXIS_STEPS.find((s) => span / s <= MAX_TICKS - 1) ?? 1
  const first = Math.floor(low / step + 1e-9)
  const last = Math.ceil(high / step - 1e-9)
  const ticks = Array.from({ length: last - first + 1 }, (_, i) => (first + i) * step)
  const [from, to] = [first * step, last * step]
  return { at: (value) => (value - from) / (to - from || 1), ticks }
}
