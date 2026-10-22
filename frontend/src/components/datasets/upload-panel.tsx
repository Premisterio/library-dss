import { UploadIcon } from "lucide-react"
import { useRef, type FormEvent } from "react"
import { toast } from "sonner"

import { useDatasetImport } from "@/api/datasets"
import { ErrorAlert } from "@/components/common/error-alert"
import { PanelCard } from "@/components/common/panel-card"
import { ImportProgress } from "@/components/datasets/import-progress"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { formText } from "@/lib/forms"

/** Upload a dataset file and follow its import live. */
export function UploadPanel() {
  const form = useRef<HTMLFormElement>(null)
  const { upload, datasetId, jobId, job, jobError, running } = useDatasetImport((finished) => {
    if (finished.status === "succeeded") toast.success("Датасет імпортовано")
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const file = data.get("file")
    if (!(file instanceof File) || file.size === 0) return
    upload.mutate(
      { file, name: formText(data, "name") },
      { onSuccess: () => form.current?.reset() }
    )
  }

  return (
    <PanelCard
      title="Завантажити датасет"
      description="JSON або JSON.gz: табличний формат симулятора libsim або вкладений формат (по користувачах)."
      contentClassName="flex flex-col gap-4"
    >
      <form ref={form} onSubmit={submit}>
        <FieldGroup className="md:flex-row md:items-end">
          <Field>
            <FieldLabel htmlFor="file">Файл</FieldLabel>
            <Input
              id="file"
              name="file"
              type="file"
              accept=".json,.gz,application/json,application/gzip"
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="name">Назва (необов'язково)</FieldLabel>
            <Input
              id="name"
              name="name"
              maxLength={200}
              placeholder="За замовчуванням — ім'я файлу"
            />
          </Field>
          <Button type="submit" disabled={running} className="md:w-auto">
            {running ? <Spinner /> : <UploadIcon />}
            Завантажити
          </Button>
        </FieldGroup>
        <FieldDescription className="mt-2">
          Імпорт іде у фоні: прогрес видно нижче, сторінку можна не оновлювати.
        </FieldDescription>
      </form>

      {upload.isError && <ErrorAlert error={upload.error} />}
      {jobId && <ImportProgress job={job} jobError={jobError} datasetId={datasetId} />}
    </PanelCard>
  )
}
