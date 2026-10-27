import { describe, expect, it } from "vitest"

import type { ChurnRun, ChurnRunDetail, Evaluation, FeatureValue, Reason } from "@/api/types"
import {
  backtestRows,
  byGroup,
  calibrationOf,
  featureValueText,
  isTraining,
  metricText,
  reasonText,
  selectRun,
} from "@/lib/churn"
import { EMPTY } from "@/lib/format"
import type { LabelFn } from "@/lib/labels"

const LABELS: Record<string, Record<string, string>> = {
  plan: { annual: "Річний", monthly: "Місячний" },
  churn_feature: { plan: "Тариф", lapsed_holds_30d: "Прострочені бронювання за 30 днів" },
}
const label: LabelFn = (group, code) => LABELS[group]?.[String(code)] ?? String(code)

function run(id: number, overrides: Partial<ChurnRun> = {}): ChurnRun {
  return {
    id,
    dataset_id: 1,
    job_id: `job-${id}`,
    status: "succeeded",
    error: null,
    active: false,
    chosen_model: "logistic",
    summary: null,
    created_at: "2026-10-27T10:00:00Z",
    finished_at: null,
    ...overrides,
  }
}

function evaluation(origin: number, model: Evaluation["model"], brier: number): Evaluation {
  return {
    origin,
    model,
    metrics: {
      members: 10,
      churned: 1,
      roc_auc: null,
      pr_auc: null,
      brier,
      brier_skill: null,
      ece: 0,
      lift: null,
      calibration: [{ predicted: brier, observed: 0, members: 10 }],
    },
  }
}

function feature(key: string, group: FeatureValue["group"]): FeatureValue {
  return { feature: key, group, value: 1, typical: 1, kind: "number", unit: "count", enum: null }
}

describe("selectRun", () => {
  const runs = [run(3), run(2, { active: true }), run(1)]

  it("takes the run in the URL, else the active one, else the newest", () => {
    expect(selectRun(runs, 1)?.id).toBe(1)
    expect(selectRun(runs, 99)?.id).toBe(2)
    expect(selectRun(runs)?.id).toBe(2)
    expect(selectRun([run(3), run(1)])?.id).toBe(3)
    expect(selectRun([])).toBeUndefined()
  })

  it("knows a run in training", () => {
    expect(isTraining(run(1, { status: "queued" }))).toBe(true)
    expect(isTraining(run(1, { status: "running" }))).toBe(true)
    expect(isTraining(run(1))).toBe(false)
    expect(isTraining(undefined)).toBe(false)
  })
})

describe("feature values", () => {
  it("shows numbers with units, flags as yes or no, codes by label", () => {
    const number = { kind: "number", unit: "ratio", enum: null } as const
    expect(featureValueText(0.5, number, label)).toMatch(/^50\s?%$/)
    expect(featureValueText(null, number, label)).toBe("немає")
    expect(featureValueText(-0.4213, { ...number, unit: null }, label)).toBe("-0,42")
    expect(featureValueText(true, { kind: "flag", unit: null, enum: null }, label)).toBe("так")
    expect(featureValueText(false, { kind: "flag", unit: null, enum: null }, label)).toBe("ні")
    expect(featureValueText("annual", { kind: "category", unit: null, enum: "plan" }, label)).toBe(
      "Річний"
    )
  })

  it("groups features in the order they come", () => {
    const features = [feature("a", "activity"), feature("p", "profile"), feature("b", "activity")]
    expect(byGroup(features).map(([group, items]) => [group, items.map((f) => f.feature)])).toEqual(
      [
        ["activity", ["a", "b"]],
        ["profile", ["p"]],
      ]
    )
  })

  it("writes a reason with the typical value", () => {
    const reason: Reason = {
      feature: "lapsed_holds_30d",
      value: 2,
      typical: 0,
      effect: 0.109,
      kind: "number",
      unit: "count",
      enum: null,
    }
    expect(reasonText(reason, label)).toBe("Прострочені бронювання за 30 днів: 2 (типово 0)")
    const plan: Reason = { ...reason, feature: "plan", value: "annual", typical: "monthly" }
    expect(reasonText({ ...plan, kind: "category", unit: null, enum: "plan" }, label)).toBe(
      "Тариф: Річний (типово Місячний)"
    )
  })
})

describe("metricText", () => {
  it("writes each metric the way it is read", () => {
    expect(metricText("roc_auc", 0.6875)).toBe("0,688")
    expect(metricText("brier", 0.05678)).toBe("0,0568")
    expect(metricText("ece", 0.0196)).toMatch(/^2\s?%$/)
    expect(metricText("lift", 2.239)).toBe("×2,24")
    expect(metricText("lift", null)).toBe(EMPTY)
  })
})

describe("run details", () => {
  const detail = {
    ...run(1),
    models: [],
    importance: [],
    coefficients: [],
    backtest: [
      evaluation(1, "logistic", 0.06),
      evaluation(0, "inactivity_rule", 0.07),
      evaluation(0, "logistic", 0.05),
    ],
  } satisfies ChurnRunDetail

  it("takes the chosen model's calibration on the newest cutoff", () => {
    expect(calibrationOf(detail)).toEqual([{ predicted: 0.05, observed: 0, members: 10 }])
    expect(calibrationOf({ ...detail, chosen_model: null })).toEqual([])
  })

  it("lays the backtest out by origin, newest first", () => {
    expect(backtestRows(detail)).toEqual([
      { origin: 0, brier: { inactivity_rule: 0.07, logistic: 0.05 } },
      { origin: 1, brier: { logistic: 0.06 } },
    ])
  })
})
