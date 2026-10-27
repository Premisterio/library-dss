/** Presentation of churn runs and scores: which run to show, values and reasons as text. */
import type {
  CalibrationBin,
  ChurnModel,
  ChurnRun,
  ChurnRunDetail,
  Described,
  FeatureValue,
  ModelSummary,
  Reason,
} from "@/api/types"
import { EMPTY, formatDecimal, formatPoints, formatValue } from "@/lib/format"
import type { LabelFn } from "@/lib/labels"

const NONE = "немає"
const TRAINING: ReadonlySet<ChurnRun["status"]> = new Set(["queued", "running"])

export function isTraining(run: ChurnRun | undefined): boolean {
  return run !== undefined && TRAINING.has(run.status)
}

/** The run asked for in the URL, else the active one, else the newest. */
export function selectRun(runs: ChurnRun[], requested?: number): ChurnRun | undefined {
  return runs.find((run) => run.id === requested) ?? runs.find((run) => run.active) ?? runs.at(0)
}

/** A feature value as text: a number with its unit, yes/no, or the label of a code. A missing
 * value means there was nothing to measure (no ratings, never read), so it reads "немає". */
export function featureValueText(
  value: Reason["value"] | undefined,
  described: Described,
  label: LabelFn
): string {
  if (value === null || value === undefined) return NONE
  switch (described.kind) {
    case "flag":
      return value === true ? "так" : "ні"
    case "category":
      return described.enum ? label(described.enum, value) : String(value)
    default:
      if (typeof value !== "number") return String(value)
      return described.unit ? formatValue(value, described.unit) : formatDecimal(value, 2)
  }
}

/** Features in their groups, groups and features in the model's order. */
export function byGroup(features: FeatureValue[]): [FeatureValue["group"], FeatureValue[]][] {
  const groups = new Map<FeatureValue["group"], FeatureValue[]>()
  for (const feature of features) {
    groups.set(feature.group, [...(groups.get(feature.group) ?? []), feature])
  }
  return [...groups.entries()]
}

/** "Прострочені бронювання за 30 днів: 2 (типово 0)". */
export function reasonText(reason: Reason, label: LabelFn): string {
  const value = featureValueText(reason.value, reason, label)
  const typical = featureValueText(reason.typical, reason, label)
  return `${label("churn_feature", reason.feature)}: ${value} (типово ${typical})`
}

/** How much a reason adds to the probability: "+11,2 в. п.". */
export function effectText(reason: Reason): string {
  return formatPoints(reason.effect)
}

export type MetricKey = Exclude<keyof ModelSummary, "model" | "origins">
export const METRICS: MetricKey[] = ["roc_auc", "pr_auc", "brier", "brier_skill", "ece", "lift"]

/** A quality metric as text: AUC "0,688", Brier "0,0568", ECE and skill as %, lift "×2,05". */
export function metricText(metric: MetricKey, value: number | null | undefined): string {
  switch (metric) {
    case "brier":
      return formatDecimal(value, 4)
    case "brier_skill":
    case "ece":
      return formatValue(value, "ratio")
    case "lift":
      return value === null || value === undefined ? EMPTY : `×${formatDecimal(value, 2)}`
    default:
      return formatDecimal(value, 3)
  }
}

/** A model's backtest means in the run. */
export function summaryOf(run: ChurnRunDetail, model: ChurnModel): ModelSummary | undefined {
  return run.models.find((summary) => summary.model === model)
}

/** The calibration bins of the chosen model on the newest test cutoff. */
export function calibrationOf(run: ChurnRunDetail): CalibrationBin[] {
  const newest = run.backtest.find((e) => e.origin === 0 && e.model === run.chosen_model)
  return newest?.metrics.calibration ?? []
}

export type BacktestRow = { origin: number; brier: Partial<Record<ChurnModel, number>> }

/** The Brier score of every model at each backtest origin, newest first. */
export function backtestRows(run: ChurnRunDetail): BacktestRow[] {
  const rows = new Map<number, BacktestRow>()
  for (const evaluation of run.backtest) {
    const row = rows.get(evaluation.origin) ?? { origin: evaluation.origin, brier: {} }
    row.brier[evaluation.model] = evaluation.metrics.brier
    rows.set(evaluation.origin, row)
  }
  return [...rows.values()].toSorted((a, b) => a.origin - b.origin)
}
