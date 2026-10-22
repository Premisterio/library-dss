import { useMutation, useQueryClient } from "@tanstack/react-query"
import { DatabaseIcon, Trash2Icon, UploadIcon } from "lucide-react"
import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link } from "react-router"
import { toast } from "sonner"

import { Capabilities, DatasetStatus } from "@/components/section-parts"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api, expectOk, unwrap } from "@/lib/api"
import { useLabel } from "@/lib/enums"
import { formatDateTime, formatDay, formatValue } from "@/lib/format"
import { isFinished, useJob } from "@/lib/jobs"
import { formText } from "@/lib/forms"
import { errorMessage, messageFor } from "@/lib/problem"
import { keys, useDatasets, type Dataset } from "@/lib/queries"

type TaskError = NonNullable<Dataset["error"]>

function ProblemList({ error }: { error: TaskError }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{messageFor(error.code, error.detail)}</AlertTitle>
      {error.errors && error.errors.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">
            {error.errors.map((problem) => (
              <li key={problem}>
                <code className="text-xs">{problem}</code>
              </li>
            ))}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  )
}

function stageText(stage: string | null | undefined, label: ReturnType<typeof useLabel>): string {
  if (!stage) return "У черзі"
  const [step, table] = stage.split(":")
  return table
    ? `${label("job_stage", step)}: ${label("dataset_table", table).toLowerCase()}`
    : label("job_stage", step)
}

function Upload() {
  const queryClient = useQueryClient()
  const label = useLabel()
  const form = useRef<HTMLFormElement>(null)
  const [jobId, setJobId] = useState<string>()
  const [datasetId, setDatasetId] = useState<number>()
  const job = useJob(jobId)

  const upload = useMutation({
    mutationFn: async ({ file, name }: { file: File; name: string }) =>
      unwrap(
        await api.POST("/api/v1/datasets", {
          body: { file: "", name: name || null }, // the serializer below sends the File itself
          bodySerializer: () => {
            const data = new FormData()
            data.append("file", file)
            if (name) data.append("name", name)
            return data
          },
        })
      ),
    onSuccess: (accepted) => {
      setJobId(accepted.job.id)
      setDatasetId(accepted.dataset.id)
      form.current?.reset()
      void queryClient.invalidateQueries({ queryKey: keys.datasets })
    },
  })

  useEffect(() => {
    if (!isFinished(job)) return
    void queryClient.invalidateQueries({ queryKey: keys.datasets })
    if (job?.status === "succeeded") toast.success("Датасет імпортовано")
  }, [job, queryClient])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const file = data.get("file")
    if (!(file instanceof File) || file.size === 0) return
    setJobId(undefined)
    upload.mutate({ file, name: formText(data, "name") })
  }

  const running = upload.isPending || (jobId !== undefined && !isFinished(job))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Завантажити датасет</CardTitle>
        <CardDescription>
          JSON або JSON.gz: табличний формат симулятора libsim або вкладений формат (по
          користувачах).
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
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

        {upload.isError && (
          <Alert variant="destructive">
            <AlertTitle>{errorMessage(upload.error)}</AlertTitle>
            {upload.error instanceof Error &&
              upload.error.message !== errorMessage(upload.error) && (
                <AlertDescription>{upload.error.message}</AlertDescription>
              )}
          </Alert>
        )}

        {jobId && (
          <div className="flex flex-col gap-2" aria-live="polite">
            <div className="flex items-center justify-between text-sm">
              <span>{job ? stageText(job.stage, label) : "Очікуємо виконавця…"}</span>
              <span className="text-muted-foreground tabular-nums">
                {formatValue(job?.progress ?? 0, "ratio")}
              </span>
            </div>
            <Progress value={(job?.progress ?? 0) * 100} />
            {job?.status === "failed" && job.error && <ProblemList error={job.error} />}
            {job?.status === "succeeded" && datasetId !== undefined && (
              <Button asChild variant="outline" className="self-start">
                <Link to={`/d/${datasetId}`}>Відкрити датасет</Link>
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function DeleteDataset({ dataset }: { dataset: Dataset }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const remove = useMutation({
    mutationFn: async () =>
      expectOk(
        await api.DELETE("/api/v1/datasets/{dataset_id}", {
          params: { path: { dataset_id: dataset.id } },
        })
      ),
    onSuccess: () => {
      setOpen(false)
      toast.success(`Датасет «${dataset.name}» видалено`)
      void queryClient.invalidateQueries({ queryKey: keys.datasets })
      void queryClient.invalidateQueries({ queryKey: ["reports"] })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button variant="ghost" size="icon" title="Видалити" onClick={() => setOpen(true)}>
        <Trash2Icon />
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Видалити датасет?</DialogTitle>
          <DialogDescription>
            «{dataset.name}» буде видалено разом з усіма даними, аналітикою та звітами. Це не можна
            скасувати.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Скасувати</Button>
          </DialogClose>
          <Button variant="destructive" disabled={remove.isPending} onClick={() => remove.mutate()}>
            {remove.isPending && <Spinner />}
            Видалити
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DatasetRow({ dataset }: { dataset: Dataset }) {
  const label = useLabel()
  const [showError, setShowError] = useState(false)
  return (
    <>
      <TableRow>
        <TableCell className="font-medium">
          {dataset.status === "ready" ? (
            <Link to={`/d/${dataset.id}`} className="hover:underline">
              {dataset.name}
            </Link>
          ) : (
            dataset.name
          )}
        </TableCell>
        <TableCell>
          {dataset.format ? (
            <Badge variant="secondary">{label("dataset_format", dataset.format)}</Badge>
          ) : (
            "—"
          )}
        </TableCell>
        <TableCell>
          <button type="button" disabled={!dataset.error} onClick={() => setShowError((v) => !v)}>
            <DatasetStatus status={dataset.status} />
          </button>
        </TableCell>
        <TableCell className="tabular-nums">
          {dataset.as_of ? formatDay(dataset.as_of) : "—"}
        </TableCell>
        <TableCell className="text-right tabular-nums">
          {dataset.row_counts.users === undefined
            ? "—"
            : formatValue(dataset.row_counts.users, "count")}
        </TableCell>
        <TableCell>
          <Capabilities capabilities={dataset.capabilities} />
        </TableCell>
        <TableCell className="text-muted-foreground">
          {formatDateTime(dataset.created_at)}
        </TableCell>
        <TableCell className="text-right">
          <DeleteDataset dataset={dataset} />
        </TableCell>
      </TableRow>
      {showError && dataset.error && (
        <TableRow>
          <TableCell colSpan={8}>
            <ProblemList error={dataset.error} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export function DatasetsPage() {
  const datasets = useDatasets()
  return (
    <>
      <Upload />
      <Card>
        <CardHeader>
          <CardTitle>Датасети</CardTitle>
          <CardDescription>
            Натисніть на назву готового датасету, щоб відкрити огляд і аналітику.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {datasets.isPending ? (
            <Skeleton className="h-24 w-full" />
          ) : datasets.isError ? (
            <Alert variant="destructive">
              <AlertTitle>{errorMessage(datasets.error)}</AlertTitle>
            </Alert>
          ) : datasets.data.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <DatabaseIcon />
                </EmptyMedia>
                <EmptyTitle>Поки що немає датасетів</EmptyTitle>
                <EmptyDescription>
                  Завантажте файл вище або виконайте <code>dss seed-demo</code>.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Назва</TableHead>
                  <TableHead>Формат</TableHead>
                  <TableHead>Стан</TableHead>
                  <TableHead>Дата зрізу</TableHead>
                  <TableHead className="text-right">Читачів</TableHead>
                  <TableHead>Можливості</TableHead>
                  <TableHead>Завантажено</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {datasets.data.map((dataset) => (
                  <DatasetRow key={dataset.id} dataset={dataset} />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  )
}
