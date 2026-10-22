import { FileTextIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { toast } from "sonner"

import { useLabel } from "@/api/enums"
import { useCreateReport } from "@/api/reports"
import type { Dataset, SectionKey } from "@/api/types"
import { PanelCard } from "@/components/common/panel-card"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { formText } from "@/lib/forms"
import { ALL_SECTIONS } from "@/lib/sections"

/** Freeze chosen analytics sections of a dataset as a report. */
export function CreateReportForm({ dataset }: { dataset: Dataset }) {
  const label = useLabel()
  const create = useCreateReport(dataset.id)
  const [chosen, setChosen] = useState<readonly SectionKey[]>(ALL_SECTIONS)

  function toggle(key: SectionKey, checked: boolean) {
    // Keep the canonical section order whatever the click order.
    setChosen((current) =>
      checked
        ? ALL_SECTIONS.filter((k) => k === key || current.includes(k))
        : current.filter((k) => k !== key)
    )
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = formText(new FormData(event.currentTarget), "title")
    if (!title || chosen.length === 0) return
    create.mutate(
      { title, sections: [...chosen] },
      { onSuccess: (report) => toast.success(`Звіт «${report.title}» створено`) }
    )
  }

  return (
    <PanelCard
      title="Новий звіт"
      description="Звіт фіксує вибрані секції аналітики на момент створення; його можна завантажити в PDF, Excel, CSV чи JSON."
    >
      <form onSubmit={submit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="title">Назва</FieldLabel>
            <Input
              id="title"
              name="title"
              required
              maxLength={200}
              defaultValue={`Звіт: ${dataset.name}`}
            />
          </Field>
          <FieldSet>
            <FieldLegend variant="label">Секції</FieldLegend>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {ALL_SECTIONS.map((key) => (
                <Field key={key} orientation="horizontal">
                  <Checkbox
                    id={`section-${key}`}
                    checked={chosen.includes(key)}
                    onCheckedChange={(checked) => toggle(key, checked === true)}
                  />
                  <FieldLabel htmlFor={`section-${key}`} className="font-normal">
                    {label("analytics_section", key)}
                  </FieldLabel>
                </Field>
              ))}
            </div>
          </FieldSet>
          <Button
            type="submit"
            className="self-start"
            disabled={create.isPending || chosen.length === 0}
          >
            {create.isPending ? <Spinner /> : <FileTextIcon />}
            Створити звіт
          </Button>
        </FieldGroup>
      </form>
    </PanelCard>
  )
}
