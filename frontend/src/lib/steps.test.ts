import { describe, expect, it } from "vitest"

import type { ChurnRun, Report } from "@/api/types"
import type { LabelFn } from "@/lib/labels"
import { decisionSteps, retentionRunId, type Step, type StepsDataset } from "@/lib/steps"

const LABELS: Record<string, Record<string, string>> = {
  churn_model: { boosting: "Бустинг", logistic: "Логістична регресія" },
}
const label: LabelFn = (group, code) => LABELS[group]?.[String(code)] ?? String(code)

function dataset(overrides: Partial<StepsDataset> = {}): StepsDataset {
  return {
    id: 1,
    as_of: "2026-09-30",
    capabilities: ["descriptive", "retention", "content"],
    row_counts: { users: 5000, loans: 120_000 },
    ...overrides,
  }
}

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

function report(id: number, overrides: Partial<Report> = {}): Report {
  return {
    id,
    dataset_id: 1,
    dataset_name: "Демо",
    kind: "retention",
    title: `Рішення ${id}`,
    params: { run_id: 7, budget: 5000 },
    sections: ["retention_plan"],
    as_of: "2026-09-30",
    timezone: "Europe/Kyiv",
    created_at: "2026-10-30T09:00:00Z",
    ...overrides,
  }
}

const NO_RETENTION = dataset({ capabilities: ["descriptive", "content"] })
const ACTIVE = run(7, { active: true, chosen_model: "boosting" })

function stepOf(steps: Step[], key: Step["key"]): Step {
  const step = steps.find((s) => s.key === key)
  if (!step) throw new Error(`no step ${key}`)
  return step
}

function accented(steps: Step[]): Step["key"][] {
  return steps.filter((step) => step.accent).map((step) => step.key)
}

describe("retentionRunId", () => {
  it("reads the run of a retention decision only when it is a number", () => {
    expect(retentionRunId(report(1))).toBe(7)
    expect(retentionRunId(report(1, { params: null }))).toBeUndefined()
    expect(retentionRunId(report(1, { params: { run_id: "7" } }))).toBeUndefined()
    expect(retentionRunId(report(1, { kind: "content", params: { run_id: 7 } }))).toBeUndefined()
  })
})

describe("decisionSteps", () => {
  it("lists the four steps in order, the data always done", () => {
    const steps = decisionSteps(dataset({ as_of: null }), [], [], label)
    expect(steps.map((step) => step.key)).toEqual(["data", "model", "plan", "content"])
    const data = stepOf(steps, "data")
    expect(data.state).toBe("done")
    expect(data.detail).toMatch(/^Читачів: 5\s000 · станом на —$/)
    expect(data.action).toEqual({ label: "Аналітика", to: "/d/1/analytics" })
    expect(data.accent).toBe(false)
  })

  it("shows a dash for a member count the dataset does not have", () => {
    const steps = decisionSteps(dataset({ row_counts: {} }), [], [], label)
    expect(stepOf(steps, "data").detail).toBe("Читачів: — · станом на 30.09.26")
  })

  it("marks the model and the plan unavailable without retention data", () => {
    const steps = decisionSteps(NO_RETENTION, [], [], label)
    for (const key of ["model", "plan"] as const) {
      expect(stepOf(steps, key)).toMatchObject({
        state: "unavailable",
        detail: "Датасет без даних кампанії утримання",
        accent: false,
      })
      expect(stepOf(steps, key).action).toBeUndefined()
    }
    expect(stepOf(steps, "content")).toMatchObject({ state: "next", accent: true })
  })

  it("asks for a model first, and the plan waits for it", () => {
    const steps = decisionSteps(dataset(), [], [], label)
    expect(stepOf(steps, "model")).toMatchObject({
      state: "next",
      detail: "Моделі ще немає",
      action: { label: "Навчити модель", to: "/d/1/churn" },
      accent: true,
    })
    const plan = stepOf(steps, "plan")
    expect(plan.state).toBe("waiting")
    expect(plan.action).toBeUndefined()
  })

  it("follows a training, with nothing accented when nothing else is next", () => {
    const capable = dataset({ capabilities: ["descriptive", "retention"] })
    const steps = decisionSteps(capable, [run(8, { status: "running" })], [], label)
    expect(stepOf(steps, "model")).toMatchObject({
      state: "running",
      action: { label: "До моделі", to: "/d/1/churn" },
    })
    expect(stepOf(steps, "content").state).toBe("unavailable")
    expect(accented(steps)).toEqual([])
  })

  it("offers to train again when the newest training failed", () => {
    const runs = [run(8, { status: "failed", chosen_model: null }), run(7)]
    expect(stepOf(decisionSteps(dataset(), runs, [], label), "model")).toMatchObject({
      state: "failed",
      detail: "Останнє навчання не вдалося",
      action: { label: "Навчити ще раз", to: "/d/1/churn" },
      accent: true,
    })
  })

  it("offers to activate a trained model", () => {
    expect(stepOf(decisionSteps(dataset(), [run(7)], [], label), "model")).toMatchObject({
      state: "next",
      detail: "Логістична регресія · 27.10.26 — не активована",
      action: { label: "Активувати", to: "/d/1/churn?run=7" },
      accent: true,
    })
  })

  it("names the active model and accents the plan", () => {
    const steps = decisionSteps(dataset(), [run(8), ACTIVE], [], label)
    expect(stepOf(steps, "model")).toMatchObject({
      state: "done",
      detail: "Бустинг · 27.10.26",
      action: { label: "До моделі", to: "/d/1/churn" },
    })
    expect(stepOf(steps, "plan")).toMatchObject({
      state: "next",
      detail: "Плану ще немає",
      action: { label: "Скласти план", to: "/d/1/churn/plan" },
    })
    expect(accented(steps)).toEqual(["plan"])
  })

  it("counts a plan approved for the active model, and the accent moves on", () => {
    const steps = decisionSteps(dataset(), [ACTIVE], [report(3, { title: "План А" })], label)
    expect(stepOf(steps, "plan")).toMatchObject({
      state: "done",
      detail: "Затверджено 30.10.26: «План А»",
      action: { label: "До звітів", to: "/d/1/reports" },
    })
    expect(accented(steps)).toEqual(["content"])
  })

  it("names a plan made for another model", () => {
    const reports = [
      report(4, { title: "Новіший", params: { run_id: 5 } }),
      report(3, { title: "Старший", params: { run_id: 4 } }),
    ]
    expect(stepOf(decisionSteps(dataset(), [ACTIVE], reports, label), "plan")).toMatchObject({
      state: "next",
      detail: "Є план для іншої моделі: «Новіший»",
      action: { label: "Скласти новий план", to: "/d/1/churn/plan" },
      accent: true,
    })
  })

  it("takes a plan without a readable run for another model's", () => {
    for (const params of [null, { run_id: "7" }]) {
      const plan = stepOf(
        decisionSteps(dataset(), [ACTIVE], [report(3, { params })], label),
        "plan"
      )
      expect(plan.state).toBe("next")
      expect(plan.detail).toBe("Є план для іншої моделі: «Рішення 3»")
    }
  })

  it("counts the newest approved portfolio", () => {
    const portfolio = { kind: "content", params: { budget: 20_000 } } as const
    const reports = [
      report(5, { ...portfolio, title: "Закупівля Б" }),
      report(4, { ...portfolio, title: "Закупівля А", created_at: "2026-10-29T09:00:00Z" }),
    ]
    expect(stepOf(decisionSteps(dataset(), [ACTIVE], reports, label), "content")).toMatchObject({
      state: "done",
      detail: "Затверджено 30.10.26: «Закупівля Б»",
      action: { label: "До звітів", to: "/d/1/reports" },
    })
  })

  it("ignores analytics reports", () => {
    const analytics = report(2, { kind: "analytics", params: null, sections: ["overview"] })
    const steps = decisionSteps(dataset(), [ACTIVE], [analytics], label)
    expect(stepOf(steps, "plan").detail).toBe("Плану ще немає")
    expect(stepOf(steps, "content")).toMatchObject({
      state: "next",
      detail: "Портфель ще не обрано",
    })
  })

  it("accents exactly one step when several are next", () => {
    const steps = decisionSteps(dataset(), [], [], label)
    expect(stepOf(steps, "content")).toMatchObject({
      state: "next",
      action: { label: "Обрати портфель", to: "/d/1/content" },
    })
    expect(accented(steps)).toEqual(["model"])
  })
})
