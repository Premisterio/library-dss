import { CalculatorIcon } from "lucide-react"
import { useState, type ComponentProps, type FormEvent } from "react"

import type { PlanIn } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { PLAN_DEFAULTS, planFrom } from "@/lib/retention"

function NumberField({
  name,
  label,
  description,
  ...input
}: { name: string; label: string; description?: string } & ComponentProps<"input">) {
  return (
    <Field>
      <FieldLabel htmlFor={name}>{label}</FieldLabel>
      <Input id={name} name={name} type="number" inputMode="decimal" {...input} />
      {description && <FieldDescription>{description}</FieldDescription>}
    </Field>
  )
}

function Toggle({
  name,
  label,
  description,
  checked,
  onCheckedChange,
}: {
  name: string
  label: string
  description: string
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}) {
  return (
    <Field orientation="horizontal">
      <Checkbox
        id={name}
        name={name}
        checked={checked}
        onCheckedChange={onCheckedChange && ((value) => onCheckedChange(value === true))}
      />
      <FieldContent>
        <FieldLabel htmlFor={name} className="font-normal">
          {label}
        </FieldLabel>
        <FieldDescription>{description}</FieldDescription>
      </FieldContent>
    </Field>
  )
}

/** The budget, limits and effects a plan is made under. */
export function PlanForm({ busy, onSubmit }: { busy: boolean; onSubmit: (plan: PlanIn) => void }) {
  const [assume, setAssume] = useState(false)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit(planFrom(new FormData(event.currentTarget)))
  }

  return (
    <PanelCard
      title="Умови плану"
      description="План вибирає, кому з групи ризику надіслати лист, а кому дати знижку на продовження, щоб очікуваний чистий виграш був найбільшим, а очікувані витрати вклалися в бюджет."
    >
      <form onSubmit={submit}>
        <FieldGroup>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <NumberField
              name="budget"
              label="Бюджет, грн"
              required
              min={0}
              max={1e9}
              step="any"
              defaultValue={PLAN_DEFAULTS.budget}
            />
            <NumberField
              name="horizon_months"
              label="Горизонт, місяців"
              description="Скільки місяців оплати утриманого читача зараховувати."
              required
              min={1}
              max={60}
              step={1}
              defaultValue={PLAN_DEFAULTS.horizonMonths}
            />
            <NumberField
              name="email_cost"
              label="Ціна листа, грн"
              required
              min={0}
              step="any"
              defaultValue={PLAN_DEFAULTS.emailCost}
            />
            <NumberField
              name="max_emails"
              label="Найбільше листів"
              description="Порожньо — без обмеження."
              min={0}
              step={1}
            />
            <NumberField
              name="max_discounts"
              label="Найбільше знижок"
              description="Порожньо — без обмеження."
              min={0}
              step={1}
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Toggle
              name="cautious"
              label="Обережний режим"
              description="Для кожного ефекту береться найменш сприятлива межа 95-відсоткового інтервалу."
            />
            <Toggle
              name="by_segment"
              label="Ефекти за сегментами"
              description="Свій ефект для кожного сегмента. На малій кампанії ці оцінки шумні й зазвичай коштують більше, ніж дають."
            />
            <Toggle
              name="assume"
              label="Задати ефекти вручну"
              description="Замість оцінених на минулій кампанії; тоді можна обрати й розмір знижки."
              checked={assume}
              onCheckedChange={setAssume}
            />
          </div>
          {assume && (
            <div className="grid gap-4 sm:grid-cols-3">
              <NumberField
                name="email_effect"
                label="Лист знижує ризик на, в. п."
                min={-100}
                max={100}
                step="any"
                defaultValue={PLAN_DEFAULTS.emailEffect}
              />
              <NumberField
                name="discount_effect"
                label="Знижка знижує ризик на, в. п."
                min={-100}
                max={100}
                step="any"
                defaultValue={PLAN_DEFAULTS.discountEffect}
              />
              <NumberField
                name="discount_pct"
                label="Знижка, %"
                min={1}
                max={99}
                step="any"
                defaultValue={PLAN_DEFAULTS.discountPct}
              />
            </div>
          )}
          <Button type="submit" className="self-start" disabled={busy}>
            {busy ? <Spinner /> : <CalculatorIcon />}
            Скласти план
          </Button>
        </FieldGroup>
      </form>
    </PanelCard>
  )
}
