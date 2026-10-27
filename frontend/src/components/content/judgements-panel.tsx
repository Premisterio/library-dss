import { TriangleAlertIcon } from "lucide-react"

import { useLabel } from "@/api/enums"
import type { Chart, Kpi } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { numberOf } from "@/lib/charts"
import { PAIRS, pairKey, ratioText, STEPS, type Step } from "@/lib/content"
import { formatValue } from "@/lib/format"
import { cn } from "@/lib/utils"

const MAX_CR = 0.1

function Scale({
  name,
  legend,
  step,
  onChange,
}: {
  name: string
  legend: string
  step: Step
  onChange: (step: Step) => void
}) {
  return (
    <fieldset className="flex justify-center gap-0.5">
      <legend className="sr-only">{legend}</legend>
      {STEPS.map((value) => (
        <label
          key={value}
          className={cn(
            "flex size-7 cursor-pointer items-center justify-center rounded-full text-xs tabular-nums transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
            value === step
              ? "bg-primary font-semibold text-primary-foreground"
              : "text-muted-foreground hover:bg-glass-hover hover:text-foreground"
          )}
        >
          <input
            type="radio"
            name={name}
            value={value}
            checked={value === step}
            onChange={() => onChange(value)}
            className="sr-only"
            aria-label={
              value === 0
                ? "однаково важливі"
                : `${value > 0 ? "лівий" : "правий"} важливіший у ${2 * Math.abs(value) + 1} рази`
            }
          />
          {2 * Math.abs(value) + 1}
        </label>
      ))}
    </fieldset>
  )
}

/** The criteria compared in pairs on Saaty's scale, and how consistent the judgements are. */
export function JudgementsPanel({
  steps,
  onChange,
  consistency,
  inconsistent,
}: {
  steps: Readonly<Record<string, Step>>
  onChange: (key: string, step: Step) => void
  consistency: Kpi | undefined
  inconsistent: Chart | undefined
}) {
  const label = useLabel()
  const cr = numberOf(consistency?.value)
  return (
    <PanelCard
      title="Порівняння критеріїв"
      description="Для кожної пари оберіть, наскільки один критерій важливіший за інший: 1 — однаково, 9 — незрівнянно важливіший. Ваги обчислюються з усіх суджень разом."
    >
      <div className="flex flex-col gap-4">
        <ul className="flex flex-col gap-3">
          {PAIRS.map((pair) => {
            const key = pairKey(pair)
            const [left, right] = pair.map((code) => label("content_criterion", code))
            return (
              <li
                key={key}
                className="grid grid-cols-2 items-center gap-x-3 gap-y-1 text-[13px] md:grid-cols-[1fr_auto_1fr]"
              >
                <span className="md:text-right">{left}</span>
                <span className="text-right md:order-3 md:text-left">{right}</span>
                <div className="col-span-2 md:order-2 md:col-span-1">
                  <Scale
                    name={`pair-${key}`}
                    legend={`${left} чи ${right}`}
                    step={steps[key] ?? 0}
                    onChange={(step) => onChange(key, step)}
                  />
                </div>
              </li>
            )
          })}
        </ul>
        {cr !== null && cr <= MAX_CR && (
          <p className="text-[13px] text-muted-foreground">
            Узгодженість суджень: CR = {formatValue(cr, "ratio")}, прийнятно (до 10 %).
          </p>
        )}
        {cr !== null && cr > MAX_CR && (
          <Alert variant="destructive">
            <TriangleAlertIcon />
            <AlertTitle>
              Судження суперечать одне одному: CR = {formatValue(cr, "ratio")}, більше за 10 %.
            </AlertTitle>
            <AlertDescription>
              <ul className="flex flex-col gap-1">
                {(inconsistent?.rows ?? []).map((row) => (
                  <li key={`${String(row.criterion)}:${String(row.compared_with)}`}>
                    {label("content_criterion", row.criterion)} проти{" "}
                    {label("content_criterion", row.compared_with)}: задано{" "}
                    {ratioText(numberOf(row.judgement_given) ?? 1)}, з рештою узгоджується ≈{" "}
                    {ratioText(numberOf(row.judgement_consistent) ?? 1)}
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </div>
    </PanelCard>
  )
}
