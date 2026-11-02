/** The steps from a dataset to its decisions and where each stands, from what the server holds. */
import type { ChurnRun, Dataset, Report } from "@/api/types"
import { paths } from "@/app/paths"
import { isTraining } from "@/lib/churn"
import { formatDay, formatLocalDay, formatValue } from "@/lib/format"
import type { LabelFn } from "@/lib/labels"
import { supportsContent, supportsRetention } from "@/lib/status"

export type StepKey = "data" | "model" | "plan" | "content"
export type StepState = "done" | "next" | "running" | "failed" | "waiting" | "unavailable"
export type Step = {
  key: StepKey
  title: string
  state: StepState
  detail: string
  action?: { label: string; to: string }
  /** The view's one accented action: on the first step that is next or failed. */
  accent: boolean
}
export type StepsDataset = Pick<Dataset, "id" | "as_of" | "capabilities" | "row_counts">

const NO_RETENTION = "Датасет без даних кампанії утримання"

/** The run a retention decision was made for: its `params.run_id`, when that is a number. */
export function retentionRunId(report: Report): number | undefined {
  if (report.kind !== "retention") return undefined
  const runId = report.params?.run_id
  return typeof runId === "number" ? runId : undefined
}

/** "Градієнтний бустинг · 27.10.26": the run's chosen model and the day it was trained. */
function runText(run: ChurnRun, label: LabelFn): string {
  return `${label("churn_model", run.chosen_model)} · ${formatLocalDay(run.created_at)}`
}

/** "Затверджено 30.10.26: «План утримання, бюджет 5 000 грн»": a decision and its day. */
export function approvedText(report: Report): string {
  return `Затверджено ${formatLocalDay(report.created_at)}: «${report.title}»`
}

function dataStep(dataset: StepsDataset): Step {
  const members = formatValue(dataset.row_counts.users, "count")
  return {
    key: "data",
    title: "Дані",
    state: "done",
    accent: false,
    detail: `Читачів: ${members} · станом на ${formatDay(dataset.as_of)}`,
    action: { label: "Аналітика", to: paths.analytics(dataset.id) },
  }
}

function modelStep(
  dataset: StepsDataset,
  runs: ChurnRun[],
  active: ChurnRun | undefined,
  label: LabelFn
): Step {
  const step = { key: "model", title: "Модель відтоку", accent: false } as const
  if (!supportsRetention(dataset)) return { ...step, state: "unavailable", detail: NO_RETENTION }
  const model = paths.churnModel(dataset.id)
  if (active) {
    const action = { label: "До моделі", to: model }
    return { ...step, state: "done", detail: runText(active, label), action }
  }
  if (runs.some(isTraining)) {
    const action = { label: "До моделі", to: model }
    return { ...step, state: "running", detail: "Навчання триває", action }
  }
  if (runs.at(0)?.status === "failed") {
    const action = { label: "Навчити ще раз", to: model }
    return { ...step, state: "failed", detail: "Останнє навчання не вдалося", action }
  }
  const trained = runs.find((run) => run.status === "succeeded")
  if (trained) {
    const action = { label: "Активувати", to: paths.churnModel(dataset.id, trained.id) }
    return { ...step, state: "next", detail: `${runText(trained, label)} — не активована`, action }
  }
  const action = { label: "Навчити модель", to: model }
  return { ...step, state: "next", detail: "Моделі ще немає", action }
}

function planStep(dataset: StepsDataset, active: ChurnRun | undefined, reports: Report[]): Step {
  const step = { key: "plan", title: "План утримання", accent: false } as const
  if (!supportsRetention(dataset)) return { ...step, state: "unavailable", detail: NO_RETENTION }
  if (!active) return { ...step, state: "waiting", detail: "Спершу потрібна активна модель" }
  const plans = reports.filter((report) => report.kind === "retention")
  const approved = plans.find((report) => retentionRunId(report) === active.id)
  if (approved) {
    const action = { label: "До звітів", to: paths.reports(dataset.id) }
    return { ...step, state: "done", detail: approvedText(approved), action }
  }
  const earlier = plans.at(0)
  if (earlier) {
    const action = { label: "Скласти новий план", to: paths.churnPlan(dataset.id) }
    return { ...step, state: "next", detail: `Є план для іншої моделі: «${earlier.title}»`, action }
  }
  const action = { label: "Скласти план", to: paths.churnPlan(dataset.id) }
  return { ...step, state: "next", detail: "Плану ще немає", action }
}

function contentStep(dataset: StepsDataset, reports: Report[]): Step {
  const step = { key: "content", title: "Закупівля контенту", accent: false } as const
  if (!supportsContent(dataset)) {
    return {
      ...step,
      state: "unavailable",
      detail: "Потрібні пропозиції дистриб'ютора й пошуки читачів",
    }
  }
  const approved = reports.find((report) => report.kind === "content")
  if (approved) {
    const action = { label: "До звітів", to: paths.reports(dataset.id) }
    return { ...step, state: "done", detail: approvedText(approved), action }
  }
  const action = { label: "Обрати портфель", to: paths.content(dataset.id) }
  return { ...step, state: "next", detail: "Портфель ще не обрано", action }
}

/**
 * The four steps from the data to the decisions: data, churn model, retention plan, content
 * portfolio. `runs` and `reports` come newest first, as the API lists them. A retention plan
 * counts only for the active model; the newest approved portfolio counts for the dataset.
 */
export function decisionSteps(
  dataset: StepsDataset,
  runs: ChurnRun[],
  reports: Report[],
  label: LabelFn
): Step[] {
  const active = runs.find((run) => run.active)
  const steps = [
    dataStep(dataset),
    modelStep(dataset, runs, active, label),
    planStep(dataset, active, reports),
    contentStep(dataset, reports),
  ]
  const first = steps.find((step) => step.state === "next" || step.state === "failed")
  if (first) first.accent = true
  return steps
}
